from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from pixelpilot.agents.observer import Observation
from pixelpilot.models import (
    ActionRequest,
    GroundedAction,
    GroundingResult,
    GroundingTier,
)

CachedLocator = Callable[[str], Awaitable[str | None]]
VisionGrounder = Callable[[str, str, bytes], Awaitable[GroundingResult]]


class Grounder:
    def __init__(
        self,
        cached_locator: CachedLocator | None = None,
        vision_grounder: VisionGrounder | None = None,
    ):
        self.cached_locator = cached_locator
        self.vision_grounder = vision_grounder

    async def ground(self, request: ActionRequest, observation: Observation) -> GroundedAction:
        if self.cached_locator is not None:
            locator = await self.cached_locator(request.intent)
            if locator:
                return GroundedAction(
                    action=request.model_copy(update={"locator": locator}),
                    tier=GroundingTier.CACHE,
                    confidence=0.98,
                    healed=True,
                )
        if request.role and request.name and self._has_role_name(request, observation):
            return GroundedAction(action=request, tier=GroundingTier.ROLE_NAME, confidence=0.95)
        if request.text and self._has_text(request.text, observation):
            return GroundedAction(
                action=request.model_copy(update={"role": None, "name": None}),
                tier=GroundingTier.DOM_TEXT,
                confidence=0.85,
            )
        if self.vision_grounder is None:
            raise LookupError(f"unable to ground intent: {request.intent}")
        image = observation.screenshot.path.read_bytes()
        started = time.perf_counter()
        found = await self.vision_grounder(request.intent, observation.page.text, image)
        vlm_ms = (time.perf_counter() - started) * 1000
        return GroundedAction(
            action=request.model_copy(
                update={"role": None, "name": None, "text": None, "bbox": found.bbox}
            ),
            tier=GroundingTier.VLM,
            confidence=found.confidence,
            vlm_ms=vlm_ms,
        )

    @staticmethod
    def _has_role_name(request: ActionRequest, observation: Observation) -> bool:
        expected = (request.name or "").casefold()
        return any(
            element.role == request.role and expected in element.name.casefold()
            for element in observation.page.elements
        )

    @staticmethod
    def _has_text(text: str, observation: Observation) -> bool:
        expected = text.casefold()
        return any(expected in element.text.casefold() for element in observation.page.elements)
