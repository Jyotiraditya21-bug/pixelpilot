from pathlib import Path
from typing import Any, cast

from typer.testing import CliRunner

from pixelpilot.cli import app
from pixelpilot.models import GroundingTier, RunRecord, StepRecord
from pixelpilot.telemetry.tracing import JsonlFileSpanExporter


class FakeSpan:
    def to_json(self, indent: int | None = 4) -> str:
        assert indent is None
        return '{"name":"step"}'


def test_jsonl_exporter_writes_file_without_console_output(tmp_path: Path, capsys: Any) -> None:
    path = tmp_path / "runs" / "traces.jsonl"
    exporter = JsonlFileSpanExporter(path)
    exporter.export([cast(Any, FakeSpan())])
    assert path.read_text() == '{"name":"step"}\n'
    assert capsys.readouterr().out == ""


def test_cli_prints_one_step_line_and_one_run_line(monkeypatch: Any, tmp_path: Path) -> None:
    story = tmp_path / "story.md"
    story.write_text("# Story\n\nSuccess: done")

    class FakeOrchestrator:
        async def run(self, *_args: object, **_kwargs: object) -> RunRecord:
            print("step=1 tier=vlm_bbox pass=true ms=12.3")
            return RunRecord(
                run_id="abc123",
                story="Story",
                passed=True,
                evidence="line one\nline two",
                steps=(
                    StepRecord(
                        number=1,
                        intent="continue",
                        success=True,
                        tier=GroundingTier.VLM,
                    ),
                ),
            )

    monkeypatch.setattr("pixelpilot.cli.Orchestrator", lambda **_kwargs: FakeOrchestrator())
    result = CliRunner().invoke(app, ["run", str(story)])
    assert result.exit_code == 0
    assert result.stdout.splitlines() == [
        "step=1 tier=vlm_bbox pass=true ms=12.3",
        "PASS abc123: line one line two",
    ]
