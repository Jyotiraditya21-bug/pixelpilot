from __future__ import annotations

import importlib
from typing import Any, cast

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter, SpanExporter
from opentelemetry.trace import Span, Tracer

_configured = False


def configure_tracing(otlp_endpoint: str | None = None) -> Tracer:
    global _configured
    if not _configured:
        provider = TracerProvider(resource=Resource.create({"service.name": "pixelpilot"}))
        exporter = _otlp_exporter(otlp_endpoint) or ConsoleSpanExporter()
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        _configured = True
    return trace.get_tracer("pixelpilot")


def _otlp_exporter(endpoint: str | None) -> SpanExporter | None:
    if not endpoint:
        return None
    try:
        module = importlib.import_module("opentelemetry.exporter.otlp.proto.grpc.trace_exporter")
        exporter_type = cast(Any, module.OTLPSpanExporter)
        return cast(SpanExporter, exporter_type(endpoint=endpoint, insecure=True))
    except (ImportError, AttributeError):
        return None


def trace_id(span: Span) -> str:
    context = span.get_span_context()
    return f"{context.trace_id:032x}" if context.is_valid else ""


def add_screenshot_event(span: Span, path: str) -> None:
    span.add_event("screenshot", {"path": path})
