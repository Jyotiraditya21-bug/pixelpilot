import io
from pathlib import Path

import pytest
from PIL import Image

from pixelpilot.agents.grounder import Grounder
from pixelpilot.agents.observer import Observation
from pixelpilot.agents.orchestrator import Orchestrator
from pixelpilot.healing.cache import HealingCache
from pixelpilot.models import (
    ActionKind,
    ActionRequest,
    BBox,
    ElementSnapshot,
    GroundingResult,
    GroundingTier,
    PageSnapshot,
    Screenshot,
)


def _observation(tmp_path: Path) -> Observation:
    path = tmp_path / "step.jpg"
    image = Image.new("RGB", (100, 100), "white")
    buffer = io.BytesIO()
    image.save(buffer, "JPEG")
    path.write_bytes(buffer.getvalue())
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
        screenshot=Screenshot(path=path, width=100, height=100),
    )


@pytest.mark.asyncio
async def test_vlm_target_auto_enrolls_and_next_lookup_uses_cache(tmp_path: Path) -> None:
    cache = HealingCache(tmp_path / "healing.db")
    orchestrator = Orchestrator(healing_cache=cache, vlm_preferred=True)
    observation = _observation(tmp_path)
    action = ActionRequest(
        kind=ActionKind.CLICK,
        intent="place the order",
        role="button",
        name="Place order",
    )
    orchestrator._enroll_vlm_target(action, observation, BBox(x=20, y=20, width=60, height=30))
    locator = await orchestrator._cached_locator(action.intent, observation)
    assert locator is not None
    calls = 0

    async def cached(_intent: str, _observation: Observation) -> str | None:
        return locator

    async def vision(_intent: str, _dom: str, _image: bytes) -> GroundingResult:
        nonlocal calls
        calls += 1
        return GroundingResult(
            bbox=BBox(x=20, y=20, width=60, height=30),
            confidence=1,
            description="button",
        )

    grounded = await Grounder(
        cached_locator=cached, vision_grounder=vision, semantic_enabled=False
    ).ground(action, observation)
    assert grounded.tier == GroundingTier.CACHE
    assert calls == 0
