"""Export recorded runs as OpenTelemetry GenAI traces and Mermaid sequence diagrams.

Everything here reads the durable event log only: no provider, tool, or MCP server is called.

* :func:`build_trace` turns one run's events into a deterministic span tree.
* :func:`render_otlp_json` encodes it as an OTLP/JSON ``ExportTraceServiceRequest`` and
  :func:`push_otlp_json` sends it to an OTLP/HTTP endpoint such as Jaeger's ``:4318/v1/traces``.
* :func:`render_mermaid` draws the run as a Mermaid ``sequenceDiagram``.
"""

from multi_bot_agentic.tracing.mermaid import mermaid_text, render_mermaid
from multi_bot_agentic.tracing.otlp import (
    DEFAULT_OTLP_TIMEOUT_SECONDS,
    SCOPE_NAME,
    SERVICE_NAME,
    OtlpExportError,
    OtlpExportResult,
    OtlpHeaderError,
    encode_any_value,
    parse_header_options,
    push_otlp_json,
    redact_url,
    render_otlp_json,
    trace_to_otlp,
    validate_endpoint,
)
from multi_bot_agentic.tracing.spans import Span, SpanEvent, SpanKind, StatusCode, Trace, build_trace
from multi_bot_agentic.tracing.timeline import RunTimeline, TraceInputError, parse_run, select_latest_run

__all__ = [
    "DEFAULT_OTLP_TIMEOUT_SECONDS",
    "SCOPE_NAME",
    "SERVICE_NAME",
    "OtlpExportError",
    "OtlpExportResult",
    "OtlpHeaderError",
    "RunTimeline",
    "Span",
    "SpanEvent",
    "SpanKind",
    "StatusCode",
    "Trace",
    "TraceInputError",
    "build_trace",
    "encode_any_value",
    "mermaid_text",
    "parse_header_options",
    "parse_run",
    "push_otlp_json",
    "redact_url",
    "render_mermaid",
    "render_otlp_json",
    "select_latest_run",
    "trace_to_otlp",
    "validate_endpoint",
]
