from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pixelpilot.agents.actor import Actor
from pixelpilot.agents.grounder import Grounder
from pixelpilot.agents.observer import Observer
from pixelpilot.agents.planner import Planner
from pixelpilot.agents.verifier import Verifier
from pixelpilot.browser.actions import perform_action
from pixelpilot.browser.session import BrowserSession
from pixelpilot.config import settings
from pixelpilot.models import (
    ActionKind,
    ActionRequest,
    BBox,
    GroundingResult,
    RunRecord,
    StepRecord,
    VisualVerification,
)
from pixelpilot.telemetry.tracing import add_screenshot_event, configure_tracing, trace_id
from pixelpilot.vision.coords import resize_for_vlm
from pixelpilot.vision.ollama_client import OllamaClient
from pixelpilot.vision.prompts import grounding_prompt, verification_prompt

MAX_STEPS = 25
STEP_TIMEOUT_SECONDS = 20.0
STEP_RETRIES = 2


class Orchestrator:
    def __init__(
        self,
        planner: Planner | None = None,
        observer: Observer | None = None,
        grounder: Grounder | None = None,
        verifier: Verifier | None = None,
    ):
        self.planner = planner or Planner()
        self.observer = observer or Observer()
        self.vision = OllamaClient(settings.ollama_url, settings.ollama_model)
        self.grounder = grounder or Grounder(vision_grounder=self._vision_ground)
        self.actor = Actor(self.grounder)
        self.verifier = verifier or Verifier(vision_verifier=self._vision_verify)
        self.tracer = configure_tracing(settings.otlp_endpoint)

    async def run(
        self,
        story_path: Path,
        base_url: str,
        *,
        mutate: bool = False,
        headless: bool = True,
        runs_dir: Path = Path("runs"),
    ) -> RunRecord:
        run_id = uuid.uuid4().hex[:12]
        url = _with_mutation(base_url, mutate)
        plan = self.planner.plan(story_path.read_text(), url)
        if len(plan.steps) > MAX_STEPS:
            raise ValueError(f"plan exceeds MAX_STEPS={MAX_STEPS}")
        records: list[StepRecord] = []
        with self.tracer.start_as_current_span(
            "pixelpilot.run", attributes={"story": plan.story}
        ) as root_span:
            current_trace_id = trace_id(root_span)
            async with BrowserSession(run_id, headless=headless, runs_dir=runs_dir) as session:
                for step in plan.steps:
                    record = await self._execute_step(session, plan.story, step.number, step.action)
                    records.append(record)
                    if not record.success:
                        break
                with self.tracer.start_as_current_span("agent.verifier") as verify_span:
                    final_observation = await self.observer.observe(session, len(records) + 1)
                    verification = await self.verifier.verify(plan.expectation, final_observation)
                    verify_span.set_attribute("pass", verification.passed)
                    add_screenshot_event(verify_span, str(final_observation.screenshot.path))
            passed = all(record.success for record in records) and verification.passed
            root_span.set_attribute("pass", passed)
        result = RunRecord(
            run_id=run_id,
            story=plan.story,
            trace_id=current_trace_id,
            passed=passed,
            evidence=verification.evidence,
            steps=tuple(records),
        )
        output = runs_dir / run_id / "run.json"
        output.write_text(result.model_dump_json(indent=2))
        return result

    async def _execute_step(
        self, session: BrowserSession, story: str, number: int, action: ActionRequest
    ) -> StepRecord:
        with self.tracer.start_as_current_span(
            "pixelpilot.step",
            attributes={"story": story, "step": number, "intent": action.intent},
        ) as step_span:
            record = await self._attempt_step(session, number, action)
            step_span.set_attribute("tier", record.tier or "direct")
            step_span.set_attribute("healed", record.healed)
            step_span.set_attribute("model", settings.ollama_model)
            step_span.set_attribute("vlm_ms", record.vlm_ms)
            step_span.set_attribute("confidence", record.confidence)
            step_span.set_attribute("pass", record.success)
            if record.screenshot:
                add_screenshot_event(step_span, str(record.screenshot))
            return record

    async def _attempt_step(
        self, session: BrowserSession, number: int, action: ActionRequest
    ) -> StepRecord:
        last_detail = "step was not attempted"
        for _attempt in range(STEP_RETRIES + 1):
            try:
                if action.kind == ActionKind.NAVIGATE:
                    with self.tracer.start_as_current_span("agent.actor"):
                        result = await asyncio.wait_for(
                            perform_action(session.require_page(), action), STEP_TIMEOUT_SECONDS
                        )
                    return StepRecord(
                        number=number,
                        intent=action.intent,
                        success=result.success,
                        detail=result.detail,
                    )
                with self.tracer.start_as_current_span("agent.observer"):
                    observation = await self.observer.observe(session, number)
                with self.tracer.start_as_current_span("agent.actor"):
                    result, grounded = await asyncio.wait_for(
                        self.actor.act(session.require_page(), action, observation),
                        STEP_TIMEOUT_SECONDS,
                    )
                if result.success:
                    return StepRecord(
                        number=number,
                        intent=action.intent,
                        success=True,
                        tier=grounded.tier,
                        healed=grounded.healed,
                        confidence=grounded.confidence,
                        vlm_ms=grounded.vlm_ms,
                        detail=result.detail,
                        screenshot=observation.screenshot.path,
                        bbox=grounded.action.bbox,
                    )
                last_detail = result.detail
            except (TimeoutError, LookupError) as exc:
                last_detail = f"{type(exc).__name__}: {exc}"
        return StepRecord(number=number, intent=action.intent, success=False, detail=last_detail)

    async def _vision_ground(self, intent: str, dom: str, image: bytes) -> GroundingResult:
        resized, transform = resize_for_vlm(image)
        result = await self.vision.complete(grounding_prompt(intent, dom), resized, GroundingResult)
        source_bbox = transform.to_source(result.bbox)
        viewport_bbox = BBox(
            x=source_bbox.x * 1280 / transform.source_width,
            y=source_bbox.y * 900 / transform.source_height,
            width=source_bbox.width * 1280 / transform.source_width,
            height=source_bbox.height * 900 / transform.source_height,
        )
        return result.model_copy(update={"bbox": viewport_bbox})

    async def _vision_verify(self, expectation: str, image: bytes) -> VisualVerification:
        resized, _ = resize_for_vlm(image)
        return await self.vision.complete(
            verification_prompt(expectation), resized, VisualVerification
        )


def _with_mutation(url: str, mutate: bool) -> str:
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query))
    query["mutate"] = str(int(mutate))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
