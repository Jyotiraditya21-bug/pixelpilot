from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict

from pixelpilot.agents.orchestrator import Orchestrator, StepCallback
from pixelpilot.config import settings
from pixelpilot.models import RunRecord, StepRecord
from pixelpilot.reporting.report import generate_report

PROJECT_ROOT = Path(__file__).parents[3]
STORIES_DIR = PROJECT_ROOT / "stories"
STATIC_INDEX = Path(__file__).with_name("static") / "index.html"


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    story: str
    url: str
    mutate: bool = False
    vlm_only: bool = False


class Runner(Protocol):
    async def run(
        self,
        story_path: Path,
        base_url: str,
        *,
        mutate: bool = False,
        headless: bool = True,
        runs_dir: Path = Path("runs"),
        run_id: str | None = None,
        on_step: StepCallback | None = None,
    ) -> RunRecord: ...


RunnerFactory = Callable[..., Runner]


@dataclass
class RunJob:
    run_id: str
    request: RunRequest
    events: list[dict[str, object]] = field(default_factory=list)
    screenshots: dict[int, Path] = field(default_factory=dict)
    condition: asyncio.Condition = field(default_factory=asyncio.Condition)
    result: RunRecord | None = None
    error: str | None = None
    finished: bool = False

    async def publish(self, event: dict[str, object]) -> None:
        async with self.condition:
            self.events.append(event)
            self.condition.notify_all()

    async def close(self) -> None:
        async with self.condition:
            self.finished = True
            self.condition.notify_all()


class DashboardService:
    def __init__(self, runner_factory: RunnerFactory = Orchestrator):
        self.runner_factory = runner_factory
        self.jobs: dict[str, RunJob] = {}
        self.tasks: set[asyncio.Task[None]] = set()

    def start(self, request: RunRequest) -> RunJob:
        run_id = uuid.uuid4().hex[:12]
        job = RunJob(run_id=run_id, request=request)
        self.jobs[run_id] = job
        task = asyncio.create_task(self._execute(job))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return job

    async def _execute(self, job: RunJob) -> None:
        async def on_step(step: StepRecord) -> None:
            if step.screenshot is not None:
                job.screenshots[step.number] = step.screenshot
            await job.publish(_step_event(job.run_id, step))

        try:
            runner = self.runner_factory(vlm_only=job.request.vlm_only)
            job.result = await runner.run(
                _story_path(job.request.story),
                job.request.url,
                mutate=job.request.mutate,
                headless=True,
                runs_dir=settings.runs_dir,
                run_id=job.run_id,
                on_step=on_step,
            )
            generate_report(settings.runs_dir / job.run_id / "run.json")
            await job.publish(
                {
                    "type": "finished",
                    "run_id": job.run_id,
                    "pass": job.result.passed,
                    "evidence": job.result.evidence,
                    "trace_id": job.result.trace_id,
                }
            )
        except Exception as exc:
            job.error = f"{type(exc).__name__}: {exc}"
            await job.publish({"type": "error", "run_id": job.run_id, "error": job.error})
        finally:
            await job.close()


def create_app(runner_factory: RunnerFactory = Orchestrator) -> FastAPI:
    dashboard_app = FastAPI(title="PixelPilot Dashboard")
    service = DashboardService(runner_factory)
    dashboard_app.state.dashboard = service

    @dashboard_app.get("/", response_class=FileResponse)
    async def index() -> FileResponse:
        return FileResponse(STATIC_INDEX)

    @dashboard_app.get("/api/stories")
    async def stories() -> list[dict[str, str]]:
        return [
            {"path": path.relative_to(PROJECT_ROOT).as_posix(), "title": _story_title(path)}
            for path in _story_files()
        ]

    @dashboard_app.post("/api/run", status_code=202)
    async def start_run(request: RunRequest) -> dict[str, str]:
        _validate_run_url(request.url)
        _story_path(request.story)
        job = service.start(request)
        return {"run_id": job.run_id}

    @dashboard_app.get("/api/runs/{run_id}/events")
    async def events(run_id: str) -> StreamingResponse:
        job = service.jobs.get(run_id)
        if job is None:
            raise HTTPException(status_code=404, detail="run not found")
        return StreamingResponse(_event_stream(job), media_type="text/event-stream")

    @dashboard_app.get("/api/runs")
    async def runs() -> list[dict[str, object]]:
        return _run_history(service)

    @dashboard_app.get("/api/runs/{run_id}/steps")
    async def saved_steps(run_id: str) -> dict[str, object]:
        run = _load_run(run_id)
        return {
            "run_id": run.run_id,
            "story": run.story,
            "pass": run.passed,
            "evidence": run.evidence,
            "trace_id": run.trace_id,
            "steps": [_step_event(run.run_id, step) for step in run.steps],
        }

    @dashboard_app.get("/api/runs/{run_id}/screenshot/{number}", response_class=FileResponse)
    async def screenshot(run_id: str, number: int) -> FileResponse:
        job = service.jobs.get(run_id)
        image_path = job.screenshots.get(number) if job else None
        if image_path is None:
            run = _load_run(run_id)
            step = next((item for item in run.steps if item.number == number), None)
            image_path = step.screenshot if step else None
        if image_path is None:
            raise HTTPException(status_code=404, detail="screenshot not found")
        image = image_path.resolve()
        run_dir = (settings.runs_dir / run_id).resolve()
        if run_dir not in image.parents or not image.is_file():
            raise HTTPException(status_code=404, detail="screenshot not found")
        return FileResponse(image, media_type="image/jpeg")

    @dashboard_app.get("/api/runs/{run_id}/report", response_class=FileResponse)
    async def report(run_id: str) -> FileResponse:
        report_path = (settings.runs_dir / run_id / "report.html").resolve()
        run_dir = (settings.runs_dir / run_id).resolve()
        if report_path.parent != run_dir or not report_path.is_file():
            raise HTTPException(status_code=404, detail="report not found")
        return FileResponse(report_path, media_type="text/html")

    return dashboard_app


def _story_files() -> tuple[Path, ...]:
    return tuple(sorted(STORIES_DIR.rglob("*.md")))


def _story_path(value: str) -> Path:
    matches = {path.relative_to(PROJECT_ROOT).as_posix(): path for path in _story_files()}
    path = matches.get(value)
    if path is None:
        raise HTTPException(status_code=404, detail="story not found")
    return path


def _story_title(path: Path) -> str:
    first_line = path.read_text().splitlines()[0].lstrip("# ").strip()
    return first_line or path.stem.replace("_", " ").title()


def _allowed_hosts() -> frozenset[str]:
    configured = urlsplit(settings.base_url).hostname
    return frozenset(host for host in (configured, "localhost", "127.0.0.1", "::1") if host)


def _validate_run_url(value: str) -> None:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in _allowed_hosts():
        raise HTTPException(status_code=400, detail="URL host is not in the run allowlist")


def _step_event(run_id: str, step: StepRecord) -> dict[str, object]:
    return {
        "type": "step",
        "run_id": run_id,
        "step": step.number,
        "intent": step.intent,
        "tier": step.tier.value if step.tier else "direct",
        "healed": step.healed,
        "vlm_ms": step.vlm_ms,
        "confidence": step.confidence,
        "pass": step.success,
        "detail": step.detail,
        "bbox": step.bbox.model_dump() if step.bbox else None,
        "screenshot": f"/api/runs/{run_id}/screenshot/{step.number}" if step.screenshot else None,
    }


async def _event_stream(job: RunJob) -> AsyncIterator[str]:
    index = 0

    def ready() -> bool:
        return index < len(job.events) or job.finished

    while True:
        async with job.condition:
            await job.condition.wait_for(ready)
            pending = job.events[index:]
            index = len(job.events)
            finished = job.finished
        for event in pending:
            yield f"event: {event['type']}\ndata: {json.dumps(event)}\n\n"
        if finished and index >= len(job.events):
            return


def _load_run(run_id: str) -> RunRecord:
    if not run_id.isalnum():
        raise HTTPException(status_code=404, detail="run not found")
    source = settings.runs_dir / run_id / "run.json"
    if not source.is_file():
        raise HTTPException(status_code=404, detail="run not found")
    return RunRecord.model_validate_json(source.read_text())


def _run_history(service: DashboardService) -> list[dict[str, object]]:
    records: dict[str, dict[str, object]] = {}
    if settings.runs_dir.exists():
        for source in settings.runs_dir.glob("*/run.json"):
            run = RunRecord.model_validate_json(source.read_text())
            records[run.run_id] = {
                "run_id": run.run_id,
                "story": run.story,
                "status": "passed" if run.passed else "failed",
                "pass": run.passed,
                "trace_id": run.trace_id,
                "vlm_ms": sum(step.vlm_ms for step in run.steps),
                "report": f"/api/runs/{run.run_id}/report",
            }
    for job in service.jobs.values():
        if job.run_id not in records:
            records[job.run_id] = {
                "run_id": job.run_id,
                "story": job.request.story,
                "status": "failed" if job.error else "running",
                "pass": False if job.error else None,
                "trace_id": "",
                "vlm_ms": sum(_event_vlm_ms(event) for event in job.events),
                "report": None,
                "error": job.error,
            }
    return list(reversed(tuple(records.values())))


def _event_vlm_ms(event: dict[str, object]) -> float:
    value = event.get("vlm_ms", 0.0)
    return float(value) if isinstance(value, int | float) else 0.0


app = create_app()
