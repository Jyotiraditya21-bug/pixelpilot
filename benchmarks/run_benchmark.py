from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import httpx
from playwright.async_api import async_playwright

from benchmarks.baseline_scripted import run_baseline
from pixelpilot.agents.orchestrator import Orchestrator

STORIES = tuple(sorted(Path("stories").glob("*.md")))
BASE_URL = "http://127.0.0.1:8000"


@dataclass(frozen=True)
class Score:
    passed: int
    total: int

    @property
    def percent(self) -> float:
        return 100 * self.passed / self.total if self.total else 0.0


async def benchmark(n: int) -> dict[tuple[str, bool], Score]:
    scores: dict[tuple[str, bool], Score] = {}
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome", headless=True)
        try:
            for mutate in (False, True):
                baseline_results = [
                    await run_baseline(browser, story, BASE_URL, mutate)
                    for story in STORIES
                    for _ in range(n)
                ]
                scores[("Scripted baseline", mutate)] = Score(
                    sum(baseline_results), len(baseline_results)
                )
        finally:
            await browser.close()
    for mutate in (False, True):
        pixelpilot_results = []
        for story in STORIES:
            for _ in range(n):
                result = await Orchestrator().run(
                    story,
                    BASE_URL,
                    mutate=mutate,
                    runs_dir=Path("runs"),
                )
                pixelpilot_results.append(result.passed)
        scores[("PixelPilot", mutate)] = Score(sum(pixelpilot_results), len(pixelpilot_results))
    for mutate in (False, True):
        vlm_results = []
        for story in STORIES:
            for _ in range(n):
                result = await Orchestrator(vlm_only=True).run(
                    story,
                    BASE_URL,
                    mutate=mutate,
                    runs_dir=Path("runs"),
                )
                vlm_results.append(result.passed)
        scores[("PixelPilot VLM-only", mutate)] = Score(sum(vlm_results), len(vlm_results))
    return scores


def write_results(scores: dict[tuple[str, bool], Score], n: int) -> Path:
    lines = [
        "# Benchmark results",
        "",
        f"Measured locally with `{n}` runs per story per mutation condition.",
        "",
        "| Runner | Mutation | Passed | Success |",
        "|---|---:|---:|---:|",
    ]
    for runner in ("Scripted baseline", "PixelPilot", "PixelPilot VLM-only"):
        for mutate in (False, True):
            score = scores[(runner, mutate)]
            lines.append(
                f"| {runner} | {int(mutate)} | {score.passed}/{score.total} | "
                f"{score.percent:.1f}% |"
            )
    baseline = scores[("Scripted baseline", True)].percent
    pixelpilot = scores[("PixelPilot", True)].percent
    lines.extend(
        (
            "",
            "Targets: scripted baseline under mutation <30%; PixelPilot under mutation ≥85%.",
            f"Observed: baseline {baseline:.1f}%, PixelPilot {pixelpilot:.1f}%.",
            "",
            "The baseline intentionally uses fixed IDs/classes. Standard PixelPilot uses "
            "accessible semantics. PixelPilot VLM-only disables cache, role/name, and DOM "
            "text so every non-navigation grounding attempt exercises Gemini REST. Missing "
            "credentials and exhausted free-tier quota are counted as failures.",
        )
    )
    output = Path("benchmarks/RESULTS.md")
    output.write_text("\n".join(lines) + "\n")
    return output


def wait_for_demo(timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if httpx.get(BASE_URL, timeout=0.5).is_success:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.1)
    raise RuntimeError("demo app did not start")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=3)
    args = parser.parse_args()
    if args.n < 1:
        parser.error("--n must be at least 1")
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "demo_app.main:app", "--port", "8000"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        wait_for_demo()
        scores = asyncio.run(benchmark(args.n))
        print(write_results(scores, args.n))
    finally:
        server.terminate()
        server.wait(timeout=5)


if __name__ == "__main__":
    main()
