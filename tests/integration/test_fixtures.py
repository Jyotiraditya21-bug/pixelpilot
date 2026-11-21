from __future__ import annotations

import asyncio
import socket
from collections.abc import AsyncIterator
from pathlib import Path
from typing import cast

import pytest
import uvicorn
from demo_app.main import app

from pixelpilot.agents.grounder import Grounder
from pixelpilot.agents.observer import Observation
from pixelpilot.agents.orchestrator import Orchestrator
from pixelpilot.agents.planner import GrammarPlanner
from pixelpilot.models import ActionRequest, GroundedAction, GroundingTier


class MockFixtureGrounder:
    async def ground(self, request: ActionRequest, _observation: Observation) -> GroundedAction:
        if "Target Widget" in request.intent:
            return GroundedAction(
                action=request.model_copy(
                    update={"locator": "article:has-text('Target Widget') button"}
                ),
                tier=GroundingTier.ROLE_NAME,
                confidence=1.0,
            )
        if "cart" in request.intent or "icon" in request.intent:
            return GroundedAction(
                action=request.model_copy(update={"locator": "button:has-text('🛒')"}),
                tier=GroundingTier.ROLE_NAME,
                confidence=1.0,
            )
        return GroundedAction(action=request, tier=GroundingTier.ROLE_NAME, confidence=1.0)


@pytest.fixture
async def demo_server() -> AsyncIterator[str]:
    sock = socket.socket()
    try:
        sock.bind(("127.0.0.1", 0))
    except PermissionError:
        sock.close()
        pytest.skip("loopback binding is unavailable in this execution sandbox")
    port = sock.getsockname()[1]
    sock.close()

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    await asyncio.sleep(0.05)

    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        await task


@pytest.mark.asyncio
async def test_scroll_fixture(demo_server: str, tmp_path: Path) -> None:
    orchestrator = Orchestrator(
        planner=GrammarPlanner(),
        grounder=cast(Grounder, MockFixtureGrounder()),
    )
    result = await orchestrator.run(
        Path("stories/fixtures/scroll.md"),
        demo_server,
        mutate=False,
        runs_dir=tmp_path / "runs",
    )
    assert result.passed
    assert "Scroll target reached and confirmed" in result.evidence

    result_mut = await orchestrator.run(
        Path("stories/fixtures/scroll.md"),
        demo_server,
        mutate=True,
        runs_dir=tmp_path / "runs",
    )
    assert result_mut.passed
    assert "Scroll target reached and confirmed" in result_mut.evidence


@pytest.mark.asyncio
async def test_modal_fixture(demo_server: str, tmp_path: Path) -> None:
    orchestrator = Orchestrator(
        planner=GrammarPlanner(),
        grounder=cast(Grounder, MockFixtureGrounder()),
    )
    result = await orchestrator.run(
        Path("stories/fixtures/modal.md"),
        demo_server,
        mutate=False,
        runs_dir=tmp_path / "runs",
    )
    assert result.passed
    assert "Special deal claimed successfully" in result.evidence

    result_mut = await orchestrator.run(
        Path("stories/fixtures/modal.md"),
        demo_server,
        mutate=True,
        runs_dir=tmp_path / "runs",
    )
    assert result_mut.passed
    assert "Special deal claimed successfully" in result_mut.evidence


@pytest.mark.asyncio
async def test_ambiguous_fixture(demo_server: str, tmp_path: Path) -> None:
    orchestrator = Orchestrator(
        planner=GrammarPlanner(),
        grounder=cast(Grounder, MockFixtureGrounder()),
    )
    result = await orchestrator.run(
        Path("stories/fixtures/ambiguous.md"),
        demo_server,
        mutate=False,
        runs_dir=tmp_path / "runs",
    )
    assert result.passed
    assert "Target Widget added to cart" in result.evidence

    result_mut = await orchestrator.run(
        Path("stories/fixtures/ambiguous.md"),
        demo_server,
        mutate=True,
        runs_dir=tmp_path / "runs",
    )
    assert result_mut.passed
    assert "Target Widget added to cart" in result_mut.evidence


@pytest.mark.asyncio
async def test_icons_fixture(demo_server: str, tmp_path: Path) -> None:
    orchestrator = Orchestrator(
        planner=GrammarPlanner(),
        grounder=cast(Grounder, MockFixtureGrounder()),
    )
    result = await orchestrator.run(
        Path("stories/fixtures/icons.md"),
        demo_server,
        mutate=False,
        runs_dir=tmp_path / "runs",
    )
    assert result.passed
    assert "Cart icon selected" in result.evidence

    result_mut = await orchestrator.run(
        Path("stories/fixtures/icons.md"),
        demo_server,
        mutate=True,
        runs_dir=tmp_path / "runs",
    )
    assert result_mut.passed
    assert "Cart icon selected" in result_mut.evidence
