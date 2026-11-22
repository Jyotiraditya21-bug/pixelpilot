from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from pixelpilot.config import settings
from pixelpilot.dashboard.app import create_app
from pixelpilot.models import GroundingTier, RunRecord, StepRecord

StepHook = Callable[[StepRecord], Awaitable[None] | None]


class MockOrchestrator:
    instances: list[MockOrchestrator] = []

    def __init__(self, *, vlm_only: bool = False):
        self.vlm_only = vlm_only
        self.calls: list[dict[str, object]] = []
        self.instances.append(self)

    async def run(
        self,
        story_path: Path,
        base_url: str,
        *,
        mutate: bool = False,
        headless: bool = True,
        runs_dir: Path = Path("runs"),
        run_id: str | None = None,
        on_step: StepHook | None = None,
    ) -> RunRecord:
        assert run_id is not None
        self.calls.append(
            {"story": story_path, "url": base_url, "mutate": mutate, "headless": headless}
        )
        steps = (
            StepRecord(
                number=1,
                intent="open catalog",
                success=True,
                tier=GroundingTier.ROLE_NAME,
                confidence=0.94,
            ),
            StepRecord(
                number=2,
                intent="select product",
                success=True,
                tier=GroundingTier.VLM if self.vlm_only else GroundingTier.CACHE,
                healed=self.vlm_only,
                vlm_ms=18.5 if self.vlm_only else 0.0,
                confidence=0.88,
            ),
        )
        for step in steps:
            if on_step is not None:
                emitted = on_step(step)
                if inspect.isawaitable(emitted):
                    await emitted
        record = RunRecord(
            run_id=run_id,
            story=story_path.stem,
            trace_id="trace-123",
            passed=True,
            evidence="Mock run completed",
            steps=steps,
        )
        run_dir = runs_dir / run_id
        run_dir.mkdir(parents=True)
        (run_dir / "run.json").write_text(record.model_dump_json())
        return record


@pytest.fixture
def dashboard_app(monkeypatch: Any, tmp_path: Path) -> FastAPI:
    MockOrchestrator.instances.clear()
    monkeypatch.setattr(settings, "runs_dir", tmp_path / "runs")
    return create_app(MockOrchestrator)


@pytest.fixture
async def client(dashboard_app: FastAPI) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=dashboard_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://dashboard.test") as value:
        yield value


@pytest.mark.asyncio
async def test_dashboard_lists_shop_and_fixture_stories(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/stories")
    assert response.status_code == 200
    paths = {item["path"] for item in response.json()}
    assert "stories/checkout_valid_coupon.md" in paths
    assert "stories/fixtures/scroll.md" in paths
    assert len(paths) == 7


@pytest.mark.asyncio
async def test_dashboard_starts_mocked_run(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/run",
        json={
            "story": "stories/checkout_valid_coupon.md",
            "url": "http://127.0.0.1:8000",
            "mutate": True,
            "vlm_only": True,
        },
    )
    assert response.status_code == 202
    assert len(response.json()["run_id"]) == 12
    await _wait_for_mock_run()
    assert MockOrchestrator.instances[0].vlm_only
    assert MockOrchestrator.instances[0].calls[0]["mutate"] is True


@pytest.mark.asyncio
async def test_dashboard_sse_preserves_step_event_order(client: httpx.AsyncClient) -> None:
    started = await client.post(
        "/api/run",
        json={
            "story": "stories/empty_cart_checkout.md",
            "url": "http://localhost:8000",
            "mutate": False,
            "vlm_only": True,
        },
    )
    run_id = started.json()["run_id"]
    response = await client.get(f"/api/runs/{run_id}/events")
    assert response.status_code == 200
    data = [
        line.removeprefix("data: ")
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    assert '"step": 1' in data[0]
    assert '"tier": "role_name"' in data[0]
    assert '"step": 2' in data[1]
    assert '"tier": "vlm_bbox"' in data[1]
    assert '"type": "finished"' in data[2]


@pytest.mark.asyncio
async def test_saved_steps_supply_replay_and_compare_data_without_new_run(
    client: httpx.AsyncClient,
) -> None:
    run_ids: list[str] = []
    for vlm_only in (False, True):
        response = await client.post(
            "/api/run",
            json={
                "story": "stories/checkout_valid_coupon.md",
                "url": "http://127.0.0.1:8000",
                "mutate": True,
                "vlm_only": vlm_only,
            },
        )
        run_ids.append(response.json()["run_id"])

    saved = await _wait_for_saved_runs(client, run_ids)
    assert len(MockOrchestrator.instances) == 2
    assert [step["step"] for step in saved[0]["steps"]] == [1, 2]
    assert saved[0]["steps"][1]["tier"] == "cached_locator"
    assert saved[0]["steps"][1]["vlm_ms"] == 0.0
    assert saved[1]["steps"][1]["tier"] == "vlm_bbox"
    assert saved[1]["steps"][1]["healed"] is True
    assert saved[1]["steps"][1]["vlm_ms"] == 18.5


@pytest.mark.asyncio
async def test_dashboard_rejects_url_outside_allowlist(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/run",
        json={
            "story": "stories/checkout_valid_coupon.md",
            "url": "https://example.com/shop",
            "mutate": False,
            "vlm_only": False,
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "URL host is not in the run allowlist"
    assert MockOrchestrator.instances == []


async def _wait_for_mock_run() -> None:
    for _ in range(20):
        if MockOrchestrator.instances and MockOrchestrator.instances[0].calls:
            return
        await asyncio.sleep(0)
    raise AssertionError("mock run did not start")


async def _wait_for_saved_runs(
    client: httpx.AsyncClient, run_ids: list[str]
) -> list[dict[str, Any]]:
    for _ in range(40):
        responses = [await client.get(f"/api/runs/{run_id}/steps") for run_id in run_ids]
        if all(response.status_code == 200 for response in responses):
            return [response.json() for response in responses]
        await asyncio.sleep(0)
    raise AssertionError("saved run data was not written")
