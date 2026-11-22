from __future__ import annotations

import asyncio
import inspect
import time
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
from playwright.async_api import Error as PlaywrightError

from pixelpilot.agents.actor import Actor
from pixelpilot.agents.grounder import Grounder
from pixelpilot.agents.observer import Observer
from pixelpilot.agents.planner import Planner
from pixelpilot.agents.verifier import Verifier
from pixelpilot.browser.actions import (
    decode_cached_locator,
    encode_cached_locator,
    perform_action,
)
from pixelpilot.browser.session import BrowserSession
from pixelpilot.config import redact_secrets, settings
from pixelpilot.healing.cache import HealingCache
from pixelpilot.healing.fingerprint import fingerprint_element
from pixelpilot.healing.strategies import fingerprint_similarity
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
StepCallback = Callable[[StepRecord], Awaitable[None] | None]


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
        self.observer = observer or Observer()
        self.vision = GeminiClient(settings.gemini_api_key.get_secret_value(), settings.vlm_model)
        self.planner = planner or Planner(client=self.vision)
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
        run_id: str | None = None,
        on_step: StepCallback | None = None,
    ) -> RunRecord:
        current_run_id = run_id or uuid.uuid4().hex[:12]
        url = _with_mutation(base_url, mutate)
        plan_res = self.planner.plan(story_path.read_text(), url)
        plan = await plan_res if inspect.isawaitable(plan_res) else plan_res
        if len(plan.steps) > MAX_STEPS:
            raise ValueError(f"plan exceeds MAX_STEPS={MAX_STEPS}")
        records: list[StepRecord] = []
        with self.tracer.start_as_current_span(
            "pixelpilot.run", attributes={"story": plan.story}
        ) as root_span:
            current_trace_id = trace_id(root_span)
            async with BrowserSession(
                current_run_id, headless=headless, runs_dir=runs_dir
            ) as session:
                for step in plan.steps:
                    record = await self._execute_step(session, plan.story, step.number, step.action)
                    records.append(record)
                    if on_step is not None:
                        callback_result = on_step(record)
                        if inspect.isawaitable(callback_result):
                            await callback_result
                    if not record.success:
                        break
                with self.tracer.start_as_current_span("agent.verifier") as verify_span:
                    try:
                        final_observation = await self.observer.observe(session, len(records) + 1)
                        verification = await asyncio.wait_for(
                            self.verifier.verify(plan.expectation, final_observation),
                            STEP_TIMEOUT_SECONDS,
                        )
                        add_screenshot_event(verify_span, str(final_observation.screenshot.path))
                    except (PlaywrightError, httpx.HTTPError, ValueError, TimeoutError) as exc:
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
            run_id=current_run_id,
            story=plan.story,
            trace_id=current_trace_id,
            passed=passed,
            evidence=verification.evidence,
            steps=tuple(records),
        )
        output = runs_dir / current_run_id / "run.json"
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
            print(
                f"step={number} tier={record.tier or 'direct'} "
                f"pass={str(record.success).lower()} ms={elapsed_ms:.1f}"
            )
            return record

    async def _attempt_step(
        self, session: BrowserSession, number: int, action: ActionRequest
    ) -> StepRecord:
        last_detail = "step was not attempted"
        last_tier: GroundingTier | None = None
        last_http_status: int | None = None
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
                        http_status=grounded.http_status,
                        detail=result.detail,
                        screenshot=observation.screenshot.path,
                        bbox=grounded.action.bbox,
                    )
                last_detail = result.detail
                last_tier = grounded.tier
                last_http_status = grounded.http_status
            except (TimeoutError, LookupError, httpx.HTTPError, ValueError, PlaywrightError) as exc:
                sensitive_value = action.value if action.kind == ActionKind.TYPE else None
                last_detail = _error_detail(exc, sensitive_value)
                if action.kind != ActionKind.NAVIGATE:
                    last_tier = GroundingTier.VLM
                    last_http_status = self.vision.last_status_code
                if isinstance(exc, httpx.HTTPStatusError):
                    last_http_status = exc.response.status_code
        return StepRecord(
            number=number,
            intent=action.intent,
            success=False,
            tier=last_tier,
            http_status=last_http_status,
            detail=last_detail,
        )

    async def _cached_locator(self, intent: str, observation: object) -> str | None:
        from pixelpilot.agents.observer import Observation

        if not isinstance(observation, Observation):
            raise TypeError("cache lookup requires an Observation")
        site = urlsplit(observation.page.url).netloc
        entry = self.healing_cache.get(site, intent)
        if entry is None:
            return None
        element = _element_for_cached_locator(entry.locator, observation.page.elements)
        if element is None:
            self.healing_cache.delete(site, intent)
            return None
        current = fingerprint_element(
            observation.screenshot.path.read_bytes(),
            element,
            observation.page.viewport_width,
            observation.page.viewport_height,
        )
        if fingerprint_similarity(entry.fingerprint, current) < 0.72:
            self.healing_cache.delete(site, intent)
            return None
        return entry.locator

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
            http_status=self.vision.last_status_code,
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


def _element_for_cached_locator(
    locator: str, elements: tuple[ElementSnapshot, ...]
) -> ElementSnapshot | None:
    payload = decode_cached_locator(locator)
    if payload is None:
        return None
    role = payload.get("role")
    name = payload.get("name", "").casefold()
    text = payload.get("text", "").casefold()
    for element in elements:
        if role and name and element.role == role and name in element.name.casefold():
            return element
        if text and text in element.text.casefold():
            return element
    return None


def _error_detail(exc: BaseException, *sensitive_values: str | None) -> str:
    message = str(exc).strip() or repr(exc)
    return redact_secrets(f"{type(exc).__name__}: {message}", *sensitive_values)
