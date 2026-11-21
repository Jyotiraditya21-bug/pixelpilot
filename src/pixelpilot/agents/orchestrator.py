from __future__ import annotations

import asyncio
import time
import uuid
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
from playwright.async_api import Error as PlaywrightError

from pixelpilot.agents.actor import Actor
from pixelpilot.agents.grounder import Grounder
from pixelpilot.agents.observer import Observer
from pixelpilot.agents.planner import Planner
from pixelpilot.agents.verifier import Verifier
from pixelpilot.browser.actions import encode_cached_locator, perform_action
from pixelpilot.browser.session import BrowserSession
from pixelpilot.config import settings
from pixelpilot.healing.cache import HealingCache
from pixelpilot.healing.fingerprint import fingerprint_element
from pixelpilot.models import (
    ActionKind,
    ActionRequest,
    BBox,
    ElementSnapshot,
    GeminiGroundingResult,
    GroundingResult,
    GroundingTier,
    RunRecord,
    StepRecord,
    VerificationResult,
    VisualVerification,
)
from pixelpilot.telemetry.tracing import add_screenshot_event, configure_tracing, trace_id
from pixelpilot.vision.coords import box_2d_to_viewport, resize_for_vlm
from pixelpilot.vision.gemini_client import GeminiClient
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
        healing_cache: HealingCache | None = None,
        vlm_only: bool = False,
        vlm_preferred: bool = False,
    ):
        self.planner = planner or Planner()
        self.observer = observer or Observer()
        self.vision = GeminiClient(settings.gemini_api_key.get_secret_value(), settings.vlm_model)
        self.healing_cache = healing_cache or HealingCache()
        self.grounder = grounder or Grounder(
            cached_locator=self._cached_locator,
            vision_grounder=self._vision_ground,
            semantic_enabled=not (vlm_only or vlm_preferred),
            cache_enabled=not vlm_only,
        )
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
                    try:
                        final_observation = await self.observer.observe(session, len(records) + 1)
                        verification = await self.verifier.verify(
                            plan.expectation, final_observation
                        )
                        add_screenshot_event(verify_span, str(final_observation.screenshot.path))
                    except (PlaywrightError, httpx.HTTPError, ValueError) as exc:
                        verification = VerificationResult(
                            passed=False,
                            evidence=f"visual verification unavailable: {_error_detail(exc)}",
                            used_vision=True,
                            confidence=0,
                        )
                    verify_span.set_attribute("pass", verification.passed)
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
            started = time.perf_counter()
            record = await self._attempt_step(session, number, action)
            elapsed_ms = (time.perf_counter() - started) * 1000
            step_span.set_attribute("tier", record.tier or "direct")
            step_span.set_attribute("healed", record.healed)
            step_span.set_attribute("model", settings.vlm_model)
            step_span.set_attribute("vlm_ms", record.vlm_ms)
            step_span.set_attribute("confidence", record.confidence)
            step_span.set_attribute("pass", record.success)
            if record.screenshot:
                add_screenshot_event(step_span, str(record.screenshot))
            line = (
                f"step={number} tier={record.tier or 'direct'} "
                f"pass={str(record.success).lower()} ms={elapsed_ms:.1f}"
            )
            if not record.success:
                line += f" error={record.detail}"
            print(line)
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
                    if result.success:
                        return StepRecord(
                            number=number,
                            intent=action.intent,
                            success=True,
                            detail=result.detail,
                        )
                    last_detail = result.detail
                    continue
                with self.tracer.start_as_current_span("agent.observer"):
                    observation = await self.observer.observe(session, number)
                with self.tracer.start_as_current_span("agent.actor"):
                    result, grounded = await asyncio.wait_for(
                        self.actor.act(session.require_page(), action, observation),
                        STEP_TIMEOUT_SECONDS,
                    )
                if result.success:
                    if grounded.tier == GroundingTier.VLM:
                        self._enroll_vlm_target(action, observation, grounded.action.bbox)
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
            except (TimeoutError, LookupError, httpx.HTTPError, ValueError) as exc:
                last_detail = _error_detail(exc)
        return StepRecord(number=number, intent=action.intent, success=False, detail=last_detail)

    async def _cached_locator(self, intent: str, observation: object) -> str | None:
        from pixelpilot.agents.observer import Observation

        if not isinstance(observation, Observation):
            raise TypeError("cache lookup requires an Observation")
        site = urlsplit(observation.page.url).netloc
        entry = self.healing_cache.get(site, intent)
        return entry.locator if entry else None

    def _enroll_vlm_target(
        self, action: ActionRequest, observation: object, bbox: BBox | None
    ) -> None:
        from pixelpilot.agents.observer import Observation

        if not isinstance(observation, Observation) or bbox is None:
            return
        locator = encode_cached_locator(action)
        element = _target_element(observation.page.elements, bbox)
        if locator is None or element is None:
            return
        fingerprint = fingerprint_element(
            observation.screenshot.path.read_bytes(),
            element,
            observation.page.viewport_width,
            observation.page.viewport_height,
        )
        site = urlsplit(observation.page.url).netloc
        self.healing_cache.put(site, action.intent, locator, fingerprint)

    async def _vision_ground(self, intent: str, dom: str, image: bytes) -> GroundingResult:
        resized, _ = resize_for_vlm(image)
        result = await self.vision.complete(
            grounding_prompt(intent, dom), resized, GeminiGroundingResult
        )
        return GroundingResult(
            bbox=box_2d_to_viewport(result.box_2d, 1280, 900),
            confidence=result.confidence,
            description=result.description,
        )

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


def _target_element(elements: tuple[ElementSnapshot, ...], bbox: BBox) -> ElementSnapshot | None:
    x, y = bbox.center
    interactive = tuple(
        element
        for element in elements
        if element.role in {"button", "link", "textbox", "combobox", "checkbox", "radio"}
    )
    containing = tuple(
        element
        for element in interactive
        if element.bbox.x <= x <= element.bbox.x + element.bbox.width
        and element.bbox.y <= y <= element.bbox.y + element.bbox.height
    )
    if containing:
        return min(containing, key=lambda element: element.bbox.width * element.bbox.height)
    if not interactive:
        return None
    return min(
        interactive,
        key=lambda element: (element.bbox.center[0] - x) ** 2 + (element.bbox.center[1] - y) ** 2,
    )


def _error_detail(exc: BaseException) -> str:
    message = str(exc).strip() or repr(exc)
    return f"{type(exc).__name__}: {message}"
