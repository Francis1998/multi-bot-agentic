"""Encode traces as OTLP/JSON and push them to an OTLP/HTTP endpoint with the standard library.

The JSON follows the OTLP 1.11.1 "JSON Protobuf Encoding": an ``ExportTraceServiceRequest``
with lowerCamelCase keys, hex-encoded ``traceId``/``spanId``/``parentSpanId``, integer enums,
and 64-bit integers (timestamps, ``intValue``) as decimal strings.
"""

from __future__ import annotations

import json
import math
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from http.client import BadStatusLine, HTTPException, UnknownProtocol
from importlib.metadata import PackageNotFoundError, version
from typing import IO, Any, Final
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from multi_bot_agentic.tracing.spans import Span, SpanEvent, SpanLink, Trace

SERVICE_NAME: Final[str] = "multi-bot-agentic"
SCOPE_NAME: Final[str] = "multi_bot_agentic.tracing"
DEFAULT_OTLP_TIMEOUT_SECONDS: Final[float] = 10.0
_MAX_RESPONSE_BYTES: Final[int] = 64 * 1024
_MAX_ERROR_BODY_CHARS: Final[int] = 300
# RFC 9110 token characters allowed in a header name.
_HEADER_NAME = re.compile(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$")
_PLACEHOLDER = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")
# Spaces and control characters, which http.client refuses anywhere in a request URL.
_URL_FORBIDDEN = re.compile(r"[\x00-\x20\x7f]")
# How a server that does not speak HTTP/1.x hangs up; a grpc-go OTLP/gRPC port resets the connection.
_HANG_UPS: Final = (ConnectionResetError, BrokenPipeError)
_NOT_HTTP1_HINT: Final[str] = (
    "; if it is an OTLP/gRPC port (4317 by default), use the OTLP/HTTP port instead "
    "(4318 by default, for example http://localhost:4318/v1/traces)"
)


class OtlpExportError(RuntimeError):
    """Raised when an OTLP/HTTP export fails. Messages never include request header values."""


class OtlpHeaderError(ValueError):
    """Raised for a malformed ``--otlp-header``. Messages never include the header value."""


@dataclass(frozen=True)
class OtlpExportResult:
    """Outcome of an accepted OTLP/HTTP export.

    Attributes:
        status: HTTP status code.
        rejected_spans: Spans the server reported as rejected (OTLP partial success).
        message: Server-provided partial-success message, if any.
    """

    status: int
    rejected_spans: int = 0
    message: str = ""


def package_version() -> str:
    """Return the installed ``multi-bot-agentic`` version (``0.0.0+unknown`` when not installed)."""

    try:
        return version(SERVICE_NAME)
    except PackageNotFoundError:
        return "0.0.0+unknown"


def trace_to_otlp(trace: Trace, *, service_version: str | None = None) -> dict[str, Any]:
    """Return the OTLP/JSON ``ExportTraceServiceRequest`` for ``trace``.

    Args:
        trace: Trace to encode.
        service_version: ``service.version`` resource attribute (defaults to the package version).

    Returns:
        JSON-serializable request body.
    """

    service_version = service_version or package_version()
    return {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": encode_attributes({"service.name": SERVICE_NAME, "service.version": service_version})
                },
                "scopeSpans": [
                    {
                        "scope": {"name": SCOPE_NAME, "version": service_version},
                        "spans": [_encode_span(span, trace.trace_id) for span in trace.spans],
                    }
                ],
            }
        ]
    }


def render_otlp_json(trace: Trace, *, indent: int | None = 2, service_version: str | None = None) -> str:
    """Serialize ``trace`` as deterministic OTLP/JSON text.

    Args:
        trace: Trace to encode.
        indent: JSON indentation; ``None`` renders compact JSON.
        service_version: Optional ``service.version`` override.

    Returns:
        JSON text (ASCII-only, so it is safe on any terminal encoding).
    """

    separators = (",", ":") if indent is None else (",", ": ")
    return json.dumps(trace_to_otlp(trace, service_version=service_version), indent=indent, separators=separators)


def encode_attributes(attributes: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Encode attributes as OTLP ``KeyValue`` objects, preserving insertion order.

    Args:
        attributes: Attribute mapping.

    Returns:
        List of ``{"key": ..., "value": AnyValue}`` objects.
    """

    return [{"key": key, "value": encode_any_value(value)} for key, value in attributes.items()]


def encode_any_value(value: Any) -> dict[str, Any]:
    """Encode a Python value as an OTLP ``AnyValue``.

    Args:
        value: String, boolean, integer, float, sequence, mapping, or ``None``.

    Returns:
        ``AnyValue`` JSON object (an empty object for ``None``).
    """

    if value is None:
        return {}
    if isinstance(value, bool):
        return {"boolValue": value}
    if isinstance(value, int):
        return {"intValue": str(value)}
    if isinstance(value, float):
        return {"doubleValue": value} if math.isfinite(value) else {"stringValue": str(value)}
    if isinstance(value, str):
        return {"stringValue": value}
    if isinstance(value, Mapping):
        return {"kvlistValue": {"values": encode_attributes({str(key): item for key, item in value.items()})}}
    if isinstance(value, (list, tuple)):
        return {"arrayValue": {"values": [encode_any_value(item) for item in value]}}
    return {"stringValue": str(value)}


def parse_header_options(options: list[str], environ: Mapping[str, str] | None = None) -> dict[str, str]:
    """Parse repeated ``KEY=VALUE`` header options.

    ``${VAR}`` and ``${VAR:-default}`` placeholders in values are expanded from the environment
    (the same syntax as MCP configs), so a token can stay out of shell history and process
    listings when the option is single-quoted.

    Args:
        options: Raw ``--otlp-header`` values.
        environ: Environment for placeholder expansion (defaults to ``os.environ``).

    Returns:
        Header mapping.

    Raises:
        OtlpHeaderError: For a missing ``=``, an invalid header name, a line break in the value,
            or an unset environment variable. Messages name the header, never its value.
    """

    source = os.environ if environ is None else environ
    headers: dict[str, str] = {}
    for index, option in enumerate(options, start=1):
        name, separator, raw_value = option.partition("=")
        name = name.strip()
        if not separator or not name:
            raise OtlpHeaderError(f"--otlp-header #{index} must look like KEY=VALUE")
        if not _HEADER_NAME.match(name):
            raise OtlpHeaderError(f"--otlp-header #{index} has an invalid header name")

        def substitute(match: re.Match[str], header: str = name) -> str:
            variable, default = match.group(1), match.group(2)
            if variable in source:
                return source[variable]
            if default is not None:
                return default
            raise OtlpHeaderError(f"--otlp-header {header}: environment variable {variable} is not set")

        value = _PLACEHOLDER.sub(substitute, raw_value.strip())
        if any(character in value for character in "\r\n\x00"):
            raise OtlpHeaderError(f"--otlp-header {name}: the value must not contain line breaks")
        headers[name] = value
    return headers


def validate_endpoint(endpoint: str) -> str:
    """Check that ``endpoint`` is an absolute ``http``/``https`` URL a request can be sent to.

    Credentials in the URL are rejected, not sent: urllib would take ``user:password@`` for part
    of the host name, and a URL argument shows up in shell history and process listings. Pass
    them with ``--otlp-header`` instead.

    Args:
        endpoint: OTLP/HTTP traces URL, for example ``http://localhost:4318/v1/traces``.

    Returns:
        The endpoint unchanged.

    Raises:
        ValueError: For other schemes, a missing host, credentials, an invalid port, a space or
            control character, or non-ASCII text in the path or query. Messages never include
            credentials.
    """

    parts = urlsplit(endpoint)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise ValueError(f"--otlp-endpoint must be an http:// or https:// URL, got {redact_url(endpoint)!r}")
    if "@" in parts.netloc:
        raise ValueError(
            "--otlp-endpoint must not contain credentials (user:password@host); send them as a header "
            "instead, for example --otlp-header 'Authorization=Basic ${OTLP_AUTH}'"
        )
    try:
        port = parts.port
    except ValueError:
        port = 0
    if port == 0:
        raise ValueError(
            f"--otlp-endpoint has an invalid port {parts.netloc.rpartition(':')[2]!r}; use a number from 1 to 65535"
        )
    if _URL_FORBIDDEN.search(endpoint.strip()) or not (parts.path + parts.query).isascii():
        raise ValueError(
            "--otlp-endpoint must be percent-encoded: it contains a space or control character, "
            "or non-ASCII text in its path or query"
        )
    return endpoint


def redact_url(url: str) -> str:
    """Return ``url`` without credentials, query, or fragment, for safe display.

    Args:
        url: URL to display.

    Returns:
        ``scheme://host[:port]/path``.
    """

    parts = urlsplit(url)
    host = parts.hostname or ""
    if ":" in host:
        host = f"[{host}]"
    try:
        port = f":{parts.port}" if parts.port is not None else ""
    except ValueError:
        port = ""
    if not parts.scheme and not host:
        return parts.path
    return f"{parts.scheme}://{host}{port}{parts.path}"


def push_otlp_json(
    body: bytes,
    endpoint: str,
    *,
    headers: Mapping[str, str] | None = None,
    timeout_seconds: float = DEFAULT_OTLP_TIMEOUT_SECONDS,
) -> OtlpExportResult:
    """POST an OTLP/JSON body to an OTLP/HTTP traces endpoint.

    Redirects are not followed, so headers such as ``Authorization`` are only ever sent to
    ``endpoint``. A 2xx answer is success; the OTLP partial-success fields are reported.

    Args:
        body: UTF-8 OTLP/JSON request body.
        endpoint: ``http``/``https`` URL, for example ``http://localhost:4318/v1/traces``.
        headers: Extra request headers (for example authentication).
        timeout_seconds: Socket timeout.

    Returns:
        Export result.

    Raises:
        OtlpExportError: On a non-2xx status, a redirect, a timeout, a connection error, an answer
            that is not HTTP/1.x or is malformed, or a host name or header HTTP/1.1 cannot carry.
        ValueError: If ``endpoint`` fails :func:`validate_endpoint`.
    """

    validate_endpoint(endpoint)
    safe_url = redact_url(endpoint)
    request_headers = {"Content-Type": "application/json", **dict(headers or {})}
    request = Request(endpoint, data=body, headers=request_headers, method="POST")
    opener = build_opener(_NoRedirect())
    try:
        with opener.open(request, timeout=timeout_seconds) as response:
            status = int(response.status)
            payload = response.read(_MAX_RESPONSE_BYTES)
    except HTTPError as error:
        detail = _error_body(error.fp) if error.fp is not None else ""
        message = f"{safe_url} answered HTTP {error.code} {error.reason}"
        raise OtlpExportError(f"{message}: {detail}" if detail else message) from None
    except URLError as error:
        reason = error.reason
        if isinstance(reason, TimeoutError):
            raise OtlpExportError(f"{safe_url} did not answer within {timeout_seconds:g}s") from None
        if isinstance(reason, _HANG_UPS):
            raise OtlpExportError(_hung_up(safe_url, reason)) from None
        raise OtlpExportError(f"cannot reach {safe_url}: {reason}") from None
    except TimeoutError:
        raise OtlpExportError(f"{safe_url} did not answer within {timeout_seconds:g}s") from None
    except _HANG_UPS as error:
        raise OtlpExportError(_hung_up(safe_url, error)) from None
    except OSError as error:
        raise OtlpExportError(f"cannot reach {safe_url}: {error}") from None
    # urllib does not wrap http.client errors (they are not OSErrors), so they are mapped here.
    except (BadStatusLine, UnknownProtocol):
        raise OtlpExportError(f"{safe_url} did not answer with HTTP/1.x{_NOT_HTTP1_HINT}") from None
    except HTTPException as error:
        raise OtlpExportError(f"the HTTP exchange with {safe_url} failed ({type(error).__name__})") from None
    except ValueError:
        # http.client quotes the offending header value in its message, so only the problem is named.
        raise OtlpExportError(
            f"cannot send the request to {safe_url}: the host name or a header has characters "
            "HTTP/1.1 cannot carry (use ASCII)"
        ) from None
    if not 200 <= status < 300:
        raise OtlpExportError(f"{safe_url} answered HTTP {status}")
    return _partial_success(status, payload)


def _hung_up(safe_url: str, error: BaseException) -> str:
    """Describe a server that closed or reset the connection instead of answering."""

    return f"{safe_url} closed the connection without an HTTP/1.x answer ({error}){_NOT_HTTP1_HINT}"


class _NoRedirect(HTTPRedirectHandler):
    """Refuse redirects so credentials never follow a ``Location`` header to another host."""

    def redirect_request(
        self,
        req: Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> Request | None:
        """Return ``None`` so urllib raises ``HTTPError`` for the 3xx answer."""

        return None


def _partial_success(status: int, payload: bytes) -> OtlpExportResult:
    """Read the optional OTLP ``partialSuccess`` object from a JSON response."""

    try:
        decoded = json.loads(payload.decode("utf-8")) if payload.strip() else {}
    except (UnicodeDecodeError, ValueError):
        return OtlpExportResult(status=status)
    partial = decoded.get("partialSuccess") if isinstance(decoded, dict) else None
    if not isinstance(partial, dict):
        return OtlpExportResult(status=status)
    try:
        rejected = int(partial.get("rejectedSpans") or 0)
    except (TypeError, ValueError):
        rejected = 0
    return OtlpExportResult(
        status=status, rejected_spans=rejected, message=_one_line(str(partial.get("errorMessage") or ""))
    )


def _error_body(stream: IO[bytes]) -> str:
    """Return a short, single-line excerpt of an error response body."""

    try:
        raw = stream.read(_MAX_ERROR_BODY_CHARS * 4)
    except (OSError, HTTPException):
        return ""
    return _one_line(raw.decode("utf-8", errors="replace"))


def _one_line(text: str) -> str:
    """Return server-provided text as one short printable line (no control characters)."""

    printable = "".join(character if character.isprintable() else " " for character in text)
    return " ".join(printable.split())[:_MAX_ERROR_BODY_CHARS]


def _encode_span(span: Span, trace_id: str) -> dict[str, Any]:
    """Encode one span as an OTLP/JSON ``Span``."""

    encoded: dict[str, Any] = {"traceId": trace_id, "spanId": span.span_id}
    if span.parent_span_id is not None:
        encoded["parentSpanId"] = span.parent_span_id
    encoded.update(
        {
            "name": span.name,
            "kind": int(span.kind),
            "startTimeUnixNano": str(span.start_time_unix_nano),
            "endTimeUnixNano": str(span.end_time_unix_nano),
            "attributes": encode_attributes(span.attributes),
        }
    )
    if span.events:
        encoded["events"] = [_encode_event(event) for event in span.events]
    if span.links:
        encoded["links"] = [_encode_link(link) for link in span.links]
    status: dict[str, Any] = {"code": int(span.status_code)}
    if span.status_message:
        status["message"] = span.status_message
    encoded["status"] = status
    return encoded


def _encode_event(event: SpanEvent) -> dict[str, Any]:
    """Encode one span event as an OTLP/JSON ``Span.Event``."""

    return {
        "timeUnixNano": str(event.time_unix_nano),
        "name": event.name,
        "attributes": encode_attributes(event.attributes),
    }


def _encode_link(link: SpanLink) -> dict[str, Any]:
    """Encode one span link as an OTLP/JSON ``Span.Link``."""

    return {"traceId": link.trace_id, "spanId": link.span_id, "attributes": encode_attributes(link.attributes)}
