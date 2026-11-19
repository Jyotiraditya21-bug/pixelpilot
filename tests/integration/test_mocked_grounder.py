from pathlib import Path
from typing import Any, cast

import pytest

from pixelpilot.agents.actor import Actor
from pixelpilot.agents.grounder import Grounder
from pixelpilot.agents.observer import Observation
from pixelpilot.models import (
    ActionKind,
    ActionRequest,
    ActionResult,
    BBox,
    GroundedAction,
    GroundingTier,
    PageSnapshot,
    Screenshot,
)


class MockGrounder:
    async def ground(self, request: ActionRequest, _observation: Observation) -> GroundedAction:
        return GroundedAction(action=request, tier=GroundingTier.ROLE_NAME, confidence=1.0)


@pytest.mark.asyncio
async def test_actor_with_mocked_grounder(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls = 0

    async def fake_action(_page: object, _action: ActionRequest) -> ActionResult:
        nonlocal calls
        calls += 1
        return ActionResult(success=calls == 2, detail="done" if calls == 2 else "retry")

    async def replan(request: ActionRequest, _detail: str) -> ActionRequest:
        return request

    monkeypatch.setattr("pixelpilot.agents.actor.perform_action", fake_action)
    image = tmp_path / "step.jpg"
    image.write_bytes(b"image")
    observation = Observation(
        page=PageSnapshot(
            url="https://example.test",
            title="test",
            text="",
            elements=(),
            viewport_width=100,
            viewport_height=100,
        ),
        screenshot=Screenshot(path=image, width=100, height=100),
    )
    request = ActionRequest(
        kind=ActionKind.CLICK,
        intent="continue",
        bbox=BBox(x=0, y=0, width=1, height=1),
    )
    actor = Actor(cast(Grounder, MockGrounder()))
    result, _ = await actor.act(cast(Any, object()), request, observation, replan)
    assert result.success
    assert calls == 2
