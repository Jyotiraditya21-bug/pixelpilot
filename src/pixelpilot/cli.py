from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
from typing import Annotated

import httpx
import typer

from pixelpilot.agents.orchestrator import Orchestrator
from pixelpilot.config import settings

app = typer.Typer(help="Mutation-resistant visual browser automation.", no_args_is_help=True)


@app.command()
def run(
    story: Annotated[Path, typer.Argument(exists=True, readable=True)],
    url: str = typer.Option(settings.base_url),
    mutate: bool = typer.Option(False, help="Enable demo DOM/CSS mutation."),
    headed: bool = typer.Option(False, help="Show Chrome."),
) -> None:
    """Run one Markdown story."""
    result = asyncio.run(
        Orchestrator().run(
            story, url, mutate=mutate, headless=not headed, runs_dir=settings.runs_dir
        )
    )
    typer.echo(f"{'PASS' if result.passed else 'FAIL'} {result.run_id}: {result.evidence}")
    raise typer.Exit(code=0 if result.passed else 1)


@app.command()
def bench(n: int = typer.Option(3, min=1)) -> None:
    """Run the benchmark harness (three runs per condition by default)."""
    command = ["uv", "run", "--no-sync", "python", "benchmarks/run_benchmark.py", "--n", str(n)]
    raise typer.Exit(subprocess.run(command, check=False).returncode)


@app.command()
def report(run_id: str) -> None:
    """Generate an HTML report from a completed run."""
    from pixelpilot.reporting.report import generate_report

    path = generate_report(settings.runs_dir / run_id / "run.json")
    typer.echo(path)


@app.command()
def doctor() -> None:
    """Check system Chrome and the local Ollama endpoint."""
    chrome = Path("/Applications/Google Chrome.app")
    chrome_ok = chrome.exists()
    try:
        response = httpx.get(f"{settings.ollama_url}/api/tags", timeout=2.0)
        ollama_ok = response.is_success
    except httpx.HTTPError:
        ollama_ok = False
    typer.echo(f"Chrome: {'ok' if chrome_ok else 'missing'} ({chrome})")
    typer.echo(f"Ollama: {'ok' if ollama_ok else 'unavailable'} ({settings.ollama_url})")
    raise typer.Exit(code=0 if chrome_ok and ollama_ok else 1)
