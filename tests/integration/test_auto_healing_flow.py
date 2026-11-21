import io
from pathlib import Path
from typing import Any, cast

import pytest
from PIL import Image

from pixelpilot.agents.observer import Observation
from pixelpilot.agents.orchestrator import Orchestrator
from pixelpilot.browser.session import BrowserSession
from pixelpilot.healing.cache import HealingCache
from pixelpilot.models import (
    ActionKind,
    ActionRequest,
    ActionResult,
    BBox,
    ElementSnapshot,
    GroundingResult,
    GroundingTier,
    PageSnapshot,
    Screenshot,
)


class MockObserver:
    def __init__(self, observation: Observation):
        self.observation = observation

    async def observe(self, _session: BrowserSession, _step: int) -> Observation:
        return self.observation


class MockSession:
    def require_page(self) -> object:
        return object()


def _observation(tmp_path: Path) -> Observation:
    screenshot = tmp_path / "step.jpg"
    image = Image.new("RGB", (100, 100), "white")
    buffer = io.BytesIO()
    image.save(buffer, "JPEG")
    screenshot.write_bytes(buffer.getvalue())
    return Observation(
        page=PageSnapshot(
            url="https://shop.test/?mutate=1",
            title="Shop",
            text="Place order",
            elements=(
                ElementSnapshot(
                    tag="button",
                    role="button",
                    name="Place order",
                    text="Place order",
                    bbox=BBox(x=20, y=20, width=60, height=30),
                ),
            ),
            viewport_width=100,
            viewport_height=100,
        ),
        screenshot=Screenshot(path=screenshot, width=100, height=100),
    )


@pytest.mark.asyncio
async def test_verified_vlm_click_enrolls_then_tier_a_uses_zero_grounding_calls(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls = 0
    observation = _observation(tmp_path)
    observer = cast(Any, MockObserver(observation))
    session = cast(BrowserSession, MockSession())
    cache = HealingCache(tmp_path / "healing.db")
    action = ActionRequest(
        kind=ActionKind.CLICK,
        intent="place the order",
        role="button",
        name="Place order",
    )

    async def mock_grounding(_intent: str, _dom: str, _image: bytes) -> GroundingResult:
        nonlocal calls
        calls += 1
        return GroundingResult(
            bbox=BBox(x=20, y=20, width=60, height=30),
            confidence=1,
            description="Place order button",
            http_status=200,
        )

    async def successful_click(_page: object, _action: ActionRequest) -> ActionResult:
        return ActionResult(success=True, detail="click verified")

    monkeypatch.setattr("pixelpilot.agents.actor.perform_action", successful_click)

    first = Orchestrator(
        observer=observer,
        healing_cache=cache,
        vlm_preferred=True,
    )
    first.grounder.vision_grounder = mock_grounding
    first_record = await first._attempt_step(session, 1, action)
    assert first_record.tier == GroundingTier.VLM
    assert first_record.success
    assert calls >= 1
    assert cache.get("shop.test", action.intent) is not None

    calls_after_first_run = calls
    second = Orchestrator(
        observer=observer,
        healing_cache=cache,
        vlm_preferred=True,
    )
    second.grounder.vision_grounder = mock_grounding
    second_record = await second._attempt_step(session, 1, action)
    assert second_record.tier == GroundingTier.CACHE
    assert second_record.success
    assert calls == calls_after_first_run
