from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
from typing import Annotated

import httpx
import typer

from pixelpilot.agents.orchestrator import Orchestrator
from pixelpilot.config import settings
from pixelpilot.vision.gemini_client import GeminiClient

app = typer.Typer(help="Mutation-resistant visual browser automation.", no_args_is_help=True)


@app.command()
def run(
    story: Annotated[Path, typer.Argument(exists=True, readable=True)],
    url: str = typer.Option(settings.base_url),
    mutate: bool = typer.Option(False, help="Enable demo DOM/CSS mutation."),
    headed: bool = typer.Option(False, help="Show Chrome."),
    vlm_only: bool = typer.Option(False, help="Skip cache and semantic grounding."),
    vlm_preferred: bool = typer.Option(
        False, help="Use cache first, then skip semantic tiers and call Gemini."
    ),
) -> None:
    """Run one Markdown story."""
    result = asyncio.run(
        Orchestrator(vlm_only=vlm_only, vlm_preferred=vlm_preferred).run(
            story, url, mutate=mutate, headless=not headed, runs_dir=settings.runs_dir
        )
    )
    evidence = " ".join(result.evidence.split())
    typer.echo(f"{'PASS' if result.passed else 'FAIL'} {result.run_id}: {evidence}")
    raise typer.Exit(code=0 if result.passed else 1)


@app.command()
def bench(n: int = typer.Option(3, min=1)) -> None:
    """Run the benchmark harness (three runs per condition by default)."""
    command = [
        "uv",
        "run",
        "--no-sync",
        "python",
        "-m",
        "benchmarks.run_benchmark",
        "--n",
        str(n),
    ]
    raise typer.Exit(subprocess.run(command, check=False).returncode)


@app.command()
def report(run_id: str) -> None:
    """Generate an HTML report from a completed run."""
    from pixelpilot.reporting.report import generate_report

    path = generate_report(settings.runs_dir / run_id / "run.json")
    typer.echo(path)


@app.command()
def doctor() -> None:
    """Check system Chrome and make one tiny live Gemini request."""
    chrome = Path("/Applications/Google Chrome.app")
    chrome_ok = chrome.exists()
    gemini_ok = bool(settings.gemini_api_key.get_secret_value())
    client = GeminiClient(
        settings.gemini_api_key.get_secret_value(), settings.vlm_model, timeout=10
    )
    try:
        status = asyncio.run(client.probe())
        live_ok = 200 <= status < 300
        live_result = str(status)
    except httpx.HTTPError as exc:
        live_ok = False
        live_result = f"{type(exc).__name__}: {exc}"
    typer.echo(f"Chrome: {'ok' if chrome_ok else 'missing'} ({chrome})")
    typer.echo(f"Gemini key: {'configured' if gemini_ok else 'missing'}")
    typer.echo(f"Gemini model: {settings.vlm_model}")
    typer.echo(f"Gemini HTTP: {live_result}")
    raise typer.Exit(code=0 if chrome_ok and gemini_ok and live_ok else 1)


@app.command()
def dashboard() -> None:
    """Serve the local run instrument panel on 127.0.0.1:8100."""
    import uvicorn

    uvicorn.run("pixelpilot.dashboard.app:app", host="127.0.0.1", port=8100)
