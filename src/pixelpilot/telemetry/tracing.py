from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult
from opentelemetry.trace import Span, Tracer

_configured = False


class JsonlFileSpanExporter(SpanExporter):
    def __init__(self, path: Path):
        self.path = path

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as output:
            for span in spans:
                output.write(span.to_json(indent=None) + "\n")
        return SpanExportResult.SUCCESS


def configure_tracing(
    _otlp_endpoint: str | None = None, trace_path: Path = Path("runs/traces.jsonl")
) -> Tracer:
    global _configured
    if not _configured:
        provider = TracerProvider(resource=Resource.create({"service.name": "pixelpilot"}))
        provider.add_span_processor(SimpleSpanProcessor(JsonlFileSpanExporter(trace_path)))
        trace.set_tracer_provider(provider)
        _configured = True
    return trace.get_tracer("pixelpilot")


def trace_id(span: Span) -> str:
    context = span.get_span_context()
    return f"{context.trace_id:032x}" if context.is_valid else ""


def add_screenshot_event(span: Span, path: str) -> None:
    span.add_event("screenshot", {"path": path})
