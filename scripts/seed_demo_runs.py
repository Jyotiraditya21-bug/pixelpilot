from __future__ import annotations

import asyncio
import subprocess
import sys
import time
from pathlib import Path

import httpx

from pixelpilot.agents.grounder import Grounder
from pixelpilot.agents.observer import Observation
from pixelpilot.agents.orchestrator import Orchestrator
from pixelpilot.agents.planner import GrammarPlanner
from pixelpilot.healing.cache import HealingCache
from pixelpilot.models import ActionRequest, GroundedAction, GroundingTier
from pixelpilot.reporting.report import generate_report

DEMO_URL = "http://127.0.0.1:8000"
STORY_PATH = Path("stories/checkout_expired_coupon.md")


class DeterministicMockGrounder(Grounder):
    def __init__(
        self,
        cached_locator: object,
        cache_enabled: bool = True,
        force_fail_intent: str | None = None,
    ):
        super().__init__(
            cached_locator=cached_locator,  # type: ignore[arg-type]
            vision_grounder=None,
            semantic_enabled=False,
            cache_enabled=cache_enabled,
        )
        self.force_fail_intent = force_fail_intent

    async def ground(self, request: ActionRequest, observation: Observation) -> GroundedAction:
        if self.force_fail_intent and self.force_fail_intent.lower() in request.intent.lower():
            raise LookupError(
                "Simulated vision grounding failure: element obscured by cookie modal overlay"
            )

        if self.cache_enabled and self.cached_locator:
            locator = await self.cached_locator(request.intent, observation)
            if locator:
                return GroundedAction(
                    action=request.model_copy(update={"locator": locator}),
                    tier=GroundingTier.CACHE,
                    confidence=0.98,
                    healed=True,
                    vlm_ms=0.0,
                )

        target = None
        for el in observation.page.elements:
            if request.name and request.name.lower() in el.name.lower():
                target = el
                break
            if request.text and request.text.lower() in el.text.lower():
                target = el
                break
        if not target and observation.page.elements:
            target = observation.page.elements[0]

        if target is None:
            raise LookupError(f"Target element not found for {request.intent}")

        # Deterministic simulated VLM latencies per step
        ms = (
            1240.0
            if "cart" in request.intent
            else (980.0 if "checkout" in request.intent else 1150.0)
        )
        return GroundedAction(
            action=request.model_copy(
                update={"bbox": target.bbox, "role": None, "name": None, "text": None}
            ),
            tier=GroundingTier.VLM,
            confidence=0.96,
            vlm_ms=ms,
        )


def _ensure_demo_server() -> subprocess.Popen[bytes] | None:
    try:
        if httpx.get(DEMO_URL, timeout=0.5).is_success:
            return None
    except httpx.HTTPError:
        pass

    server = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "demo_app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        try:
            if httpx.get(DEMO_URL, timeout=0.5).is_success:
                return server
        except httpx.HTTPError:
            pass
        time.sleep(0.1)
    server.terminate()
    raise RuntimeError("demo app failed to start on 127.0.0.1:8000")


async def seed_demo_runs(runs_dir: Path = Path("runs")) -> list[str]:
    runs_dir.mkdir(parents=True, exist_ok=True)
    cache_path = runs_dir / "demo_healing.db"
    cache_path.unlink(missing_ok=True)
    shared_cache = HealingCache(cache_path)

    run_ids = ["seed01vlmheal", "seed02cachhit", "seed03failerr"]

    # Run 1: Heals through vision tier (vlm_bbox)
    orch1 = Orchestrator(planner=GrammarPlanner(), healing_cache=shared_cache)
    orch1.grounder = DeterministicMockGrounder(orch1._cached_locator, cache_enabled=True)
    orch1.actor.grounder = orch1.grounder
    res1 = await orch1.run(
        STORY_PATH,
        DEMO_URL,
        mutate=True,
        runs_dir=runs_dir,
        run_id=run_ids[0],
    )
    generate_report(runs_dir / run_ids[0] / "run.json")
    print(
        f"Seeded Run 1 ({run_ids[0]}): passed={res1.passed}, tiers={[s.tier for s in res1.steps]}"
    )

    # Run 2: Resolves from cache at tier (a) with 0 ms
    orch2 = Orchestrator(planner=GrammarPlanner(), healing_cache=shared_cache)
    orch2.grounder = DeterministicMockGrounder(orch2._cached_locator, cache_enabled=True)
    orch2.actor.grounder = orch2.grounder
    res2 = await orch2.run(
        STORY_PATH,
        DEMO_URL,
        mutate=True,
        runs_dir=runs_dir,
        run_id=run_ids[1],
    )
    generate_report(runs_dir / run_ids[1] / "run.json")
    print(
        f"Seeded Run 2 ({run_ids[1]}): passed={res2.passed}, tiers={[s.tier for s in res2.steps]}"
    )

    # Run 3: Failed run for error state
    orch3 = Orchestrator(planner=GrammarPlanner(), healing_cache=shared_cache)
    orch3.grounder = DeterministicMockGrounder(
        orch3._cached_locator, cache_enabled=False, force_fail_intent="coupon"
    )
    orch3.actor.grounder = orch3.grounder
    res3 = await orch3.run(
        STORY_PATH,
        DEMO_URL,
        mutate=True,
        runs_dir=runs_dir,
        run_id=run_ids[2],
    )
    generate_report(runs_dir / run_ids[2] / "run.json")
    print(f"Seeded Run 3 ({run_ids[2]}): passed={res3.passed}")

    return run_ids


def main() -> None:
    server = _ensure_demo_server()
    try:
        asyncio.run(seed_demo_runs())
    finally:
        if server is not None:
            server.terminate()
            server.wait(timeout=5)


if __name__ == "__main__":
    main()
