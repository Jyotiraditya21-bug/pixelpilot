from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import SecretStr

from pixelpilot.agents.orchestrator import _error_detail
from pixelpilot.browser.actions import perform_action
from pixelpilot.browser.dom_snapshot import _SNAPSHOT_SCRIPT, snapshot_page
from pixelpilot.config import settings
from pixelpilot.models import ActionKind, ActionRequest, BBox, StepRecord
from pixelpilot.telemetry.tracing import JsonlFileSpanExporter


class SnapshotPage:
    async def evaluate(self, _script: str) -> dict[str, object]:
        return {
            "url": "http://localhost/login",
            "title": "Login",
            "text": "Password",
            "elements": [
                {
                    "tag": "input",
                    "role": "textbox",
                    "name": "Password",
                    "text": "[REDACTED]",
                    "bbox": {"x": 4, "y": 8, "width": 160, "height": 32},
                }
            ],
            "viewport_width": 800,
            "viewport_height": 600,
        }


class Mouse:
    async def click(self, _x: float, _y: float) -> None:
        return None


class ExplodingKeyboard:
    async def insert_text(self, value: str) -> None:
        raise RuntimeError(f"driver could not type {value}")


class TypePage:
    mouse = Mouse()
    keyboard = ExplodingKeyboard()


class SpanJson:
    def __init__(self, detail: str):
        self.detail = detail

    def to_json(self, indent: int | None = 4) -> str:
        assert indent is None
        return f'{{"detail":{self.detail!r}}}'


@pytest.mark.asyncio
async def test_password_snapshot_and_failed_type_redact_typed_value() -> None:
    typed_secret = "correct-horse-battery-staple"
    assert "n.type === 'password'" in _SNAPSHOT_SCRIPT
    assert "secret ? '[REDACTED]'" in _SNAPSHOT_SCRIPT

    snapshot = await snapshot_page(cast(Any, SnapshotPage()))
    assert typed_secret not in snapshot.model_dump_json()
    assert snapshot.elements[0].text == "[REDACTED]"

    result = await perform_action(
        cast(Any, TypePage()),
        ActionRequest(
            kind=ActionKind.TYPE,
            intent="enter password",
            value=typed_secret,
            bbox=BBox(x=10, y=10, width=80, height=20),
        ),
    )
    assert not result.success
    assert typed_secret not in result.detail
    assert "[REDACTED]" in result.detail
    record = StepRecord(number=1, intent="enter password", success=False, detail=result.detail)
    assert typed_secret not in record.model_dump_json()


def test_gemini_key_is_absent_from_errors_logs_spans_and_trace_file(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    api_key = "gemini-test-key-that-must-never-appear"
    monkeypatch.setattr(settings, "gemini_api_key", SecretStr(api_key))
    detail = _error_detail(RuntimeError(f"provider rejected {api_key}"))
    assert api_key not in detail
    assert "[REDACTED]" in detail

    with caplog.at_level(logging.ERROR):
        logging.getLogger("pixelpilot.test").error("%s", detail)
    assert api_key not in caplog.text

    trace_path = tmp_path / "runs" / "traces.jsonl"
    JsonlFileSpanExporter(trace_path).export([cast(Any, SpanJson(detail))])
    assert api_key not in trace_path.read_text()
