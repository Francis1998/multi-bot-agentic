"""CLI tests for ``trace``: formats, run selection, errors, and the OTLP/HTTP push."""

from __future__ import annotations

import json
import socket
import struct
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from multi_bot_agentic.cli import build_parser, run_command, trace_command
from multi_bot_agentic.event_log import SQLiteEventLog
from multi_bot_agentic.tracing import build_trace, render_otlp_json

GOAL = "Create a launch checklist for an AI agent platform"
TOKEN = "otlp-test-token-0123456789"
# The HTTP/2 SETTINGS frame a gRPC server sends first; an HTTP/1.1 client cannot parse it.
HTTP2_SETTINGS_FRAME = b"\x00\x00\x06\x04\x00\x00\x00\x00\x00\x00\x05\x00\x00\x40\x00"
NOT_HTTP1_HINT = "use the OTLP/HTTP port instead (4318 by default"


@dataclass(frozen=True)
class _Request:
    """One request received by the OTLP stub."""

    path: str
    headers: dict[str, str]
    body: bytes


@dataclass(frozen=True)
class _Stub:
    """A running OTLP/HTTP stub."""

    url: str
    received: list[_Request]


@contextmanager
def _otlp_stub(status: int = 200, body: bytes = b"{}", location: str | None = None) -> Iterator[_Stub]:
    """Serve a local OTLP/HTTP receiver in a thread that records every request."""

    received: list[_Request] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            headers = {key.lower(): value for key, value in self.headers.items()}
            received.append(_Request(path=self.path, headers=headers, body=self.rfile.read(length)))
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            if location is not None:
                self.send_header("Location", location)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args: Any) -> None:
            del args

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield _Stub(url=f"http://127.0.0.1:{server.server_port}/v1/traces", received=received)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@contextmanager
def _raw_responder(reply: bytes | None) -> Iterator[str]:
    """Read one whole request, then answer with raw ``reply`` bytes or, for ``None``, reset the connection.

    Reading the request first means the client fails on the answer itself, the way it does
    against a gRPC port, and never while still writing its body.
    """

    listener = socket.create_server(("127.0.0.1", 0))
    listener.settimeout(10)

    def serve() -> None:
        connection, _ = listener.accept()
        with connection:
            data = b""
            while b"\r\n\r\n" not in data:
                chunk = connection.recv(65536)
                if not chunk:
                    return
                data += chunk
            head, _, body = data.partition(b"\r\n\r\n")
            lines = head.lower().split(b"\r\n")
            length = next(int(line.split(b":")[1]) for line in lines if line.startswith(b"content-length:"))
            while len(body) < length:
                chunk = connection.recv(65536)
                if not chunk:
                    return
                body += chunk
            if reply is None:
                connection.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
            else:
                connection.sendall(reply)

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{listener.getsockname()[1]}/v1/traces"
    finally:
        thread.join(timeout=5)
        listener.close()


def _run(event_log: Path, run_id: str, capsys: pytest.CaptureFixture[str]) -> None:
    """Record a fake-provider run through the real ``run`` command."""

    args = build_parser().parse_args(
        [
            "run",
            "--goal",
            GOAL,
            "--provider",
            "fake",
            "--max-steps",
            "5",
            "--event-log",
            str(event_log),
            "--run-id",
            run_id,
        ]
    )
    assert run_command(args) == 0
    capsys.readouterr()


def _trace(*argv: str) -> int:
    return trace_command(build_parser().parse_args(["trace", *argv]))


def _events(event_log: Path, run_id: str) -> Any:
    log = SQLiteEventLog(event_log)
    try:
        return log.list_events(run_id)
    finally:
        log.close()


def test_trace_defaults_to_the_latest_run_and_prints_otlp_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Without --run-id the most recently active run is exported as OTLP/JSON on stdout."""

    event_log = tmp_path / "runs.sqlite"
    _run(event_log, "first", capsys)
    _run(event_log, "second", capsys)

    assert _trace("--event-log", str(event_log)) == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    spans = payload["resourceSpans"][0]["scopeSpans"][0]["spans"]
    assert [span["name"] for span in spans] == ["invoke_agent", "chat", "execute_tool checklist", "chat"]
    root_attributes = {item["key"]: item["value"] for item in spans[0]["attributes"]}
    assert root_attributes["gen_ai.conversation.id"] == {"stringValue": "second"}
    assert "tracing the most recent run second" in captured.err
    assert captured.out == render_otlp_json(build_trace(_events(event_log, "second"))) + "\n"

    assert _trace("--event-log", str(event_log), "--run-id", "first") == 0
    assert '"stringValue": "first"' in capsys.readouterr().out


def test_trace_writes_mermaid_and_content_to_files(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """--format mermaid and --output write a file; --include-content adds redacted content."""

    event_log = tmp_path / "runs.sqlite"
    _run(event_log, "files", capsys)
    diagram = tmp_path / "out" / "run.mmd"
    otlp = tmp_path / "out" / "run.json"

    assert _trace("--event-log", str(event_log), "--format", "mermaid", "--output", str(diagram)) == 0
    assert _trace("--event-log", str(event_log), "--output", str(otlp), "--include-content") == 0
    captured = capsys.readouterr()

    assert captured.out == ""
    assert f"wrote mermaid trace of run files to {diagram}" in captured.err
    text = diagram.read_text(encoding="utf-8")
    assert text.startswith("sequenceDiagram\n") and text.endswith("    Note over O: succeeded after 4 steps\n")
    assert "gen_ai.input.messages" in otlp.read_text(encoding="utf-8")


def test_trace_reports_missing_logs_unknown_runs_and_empty_logs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Input problems exit with code 2 and a one-line error, without creating files."""

    missing = tmp_path / "missing.sqlite"
    assert _trace("--event-log", str(missing)) == 2
    assert f"error: event log not found: {missing}" in capsys.readouterr().err
    assert not missing.exists()

    event_log = tmp_path / "runs.sqlite"
    _run(event_log, "known", capsys)
    assert _trace("--event-log", str(event_log), "--run-id", "unknown") == 2
    assert f"error: run unknown not found in event log {event_log}" in capsys.readouterr().err

    empty = tmp_path / "empty.sqlite"
    SQLiteEventLog(empty).close()
    assert _trace("--event-log", str(empty)) == 2
    assert f"error: event log {empty} has no runs" in capsys.readouterr().err

    not_sqlite = tmp_path / "notes.txt"
    not_sqlite.write_text("not a database " * 100, encoding="utf-8")
    assert _trace("--event-log", str(not_sqlite)) == 2
    assert f"error: cannot read event log {not_sqlite}" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (["--otlp-endpoint", "http://localhost:4318/v1/traces", "--otlp-header", "Authorization"], "KEY=VALUE"),
        (["--otlp-endpoint", "http://localhost:4318/v1/traces", "--otlp-header", "bad name=x"], "invalid header"),
        (
            ["--otlp-endpoint", "http://localhost:4318/v1/traces", "--otlp-header", "X-Key=${TRACE_UNSET_VARIABLE}"],
            "environment variable TRACE_UNSET_VARIABLE is not set",
        ),
        (["--otlp-endpoint", "ftp://localhost/v1/traces"], "must be an http:// or https:// URL"),
        (["--otlp-header", "Authorization=Bearer x"], "--otlp-header requires --otlp-endpoint"),
        (["--otlp-endpoint", "http://localhost:4318/v1/traces", "--otlp-timeout", "0"], "--otlp-timeout must be > 0"),
    ],
)
def test_trace_rejects_invalid_arguments(
    argv: list[str],
    message: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invalid OTLP options exit with code 2 before the event log is read."""

    monkeypatch.delenv("TRACE_UNSET_VARIABLE", raising=False)
    assert _trace("--event-log", str(tmp_path / "runs.sqlite"), *argv) == 2
    error = capsys.readouterr().err
    assert message in error
    assert "Bearer x" not in error


def test_trace_rejects_an_unknown_format(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """argparse rejects formats other than otlp-json and mermaid."""

    with pytest.raises(SystemExit) as exit_info:
        build_parser().parse_args(["trace", "--event-log", str(tmp_path / "x.sqlite"), "--format", "zipkin"])
    assert exit_info.value.code == 2
    assert "invalid choice: 'zipkin'" in capsys.readouterr().err


def test_trace_pushes_otlp_json_to_an_otlp_http_endpoint(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """--otlp-endpoint POSTs the OTLP/JSON body with its headers and prints only a summary."""

    monkeypatch.setenv("TRACE_TEST_TOKEN", TOKEN)
    event_log = tmp_path / "runs.sqlite"
    _run(event_log, "pushed", capsys)

    with _otlp_stub() as stub:
        code = _trace(
            "--event-log",
            str(event_log),
            "--otlp-endpoint",
            stub.url,
            "--otlp-header",
            "Authorization=Bearer ${TRACE_TEST_TOKEN}",
            "--otlp-header",
            "X-Scope-OrgID=team-a",
        )
    captured = capsys.readouterr()

    assert code == 0
    (request,) = stub.received
    assert request.path == "/v1/traces"
    assert request.headers["content-type"] == "application/json"
    assert request.headers["authorization"] == f"Bearer {TOKEN}"
    assert request.headers["x-scope-orgid"] == "team-a"
    assert json.loads(request.body) == json.loads(render_otlp_json(build_trace(_events(event_log, "pushed"))))
    assert captured.out == ""
    assert (
        f"exported 4 spans of run pushed (trace {build_trace(_events(event_log, 'pushed')).trace_id})" in captured.err
    )
    assert f"to {stub.url}: HTTP 200" in captured.err
    assert TOKEN not in captured.err


def test_trace_can_print_mermaid_and_push_in_one_command(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """--format still controls stdout when a push is requested."""

    event_log = tmp_path / "runs.sqlite"
    _run(event_log, "both", capsys)

    with _otlp_stub() as stub:
        assert _trace("--event-log", str(event_log), "--format", "mermaid", "--otlp-endpoint", stub.url) == 0

    assert capsys.readouterr().out.startswith("sequenceDiagram\n")
    assert len(stub.received) == 1


def test_trace_push_failure_exits_1_without_leaking_headers(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A non-2xx answer is an error with the status and a body excerpt, never the header values."""

    event_log = tmp_path / "runs.sqlite"
    _run(event_log, "rejected", capsys)

    with _otlp_stub(status=500, body=b'{"message": "storage unavailable"}') as stub:
        code = _trace("--event-log", str(event_log), "--otlp-endpoint", stub.url, "--otlp-header", f"X-Token={TOKEN}")
    error = capsys.readouterr().err

    assert code == 1
    assert "error: OTLP export failed:" in error
    assert "answered HTTP 500" in error
    assert "storage unavailable" in error
    assert TOKEN not in error


def test_trace_push_does_not_follow_redirects(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A redirect is reported as a failure so credentials never follow a Location header."""

    event_log = tmp_path / "runs.sqlite"
    _run(event_log, "redirected", capsys)

    with _otlp_stub(status=307, location="http://127.0.0.1:9/elsewhere") as stub:
        code = _trace("--event-log", str(event_log), "--otlp-endpoint", stub.url, "--otlp-header", f"X-Token={TOKEN}")

    assert code == 1
    assert len(stub.received) == 1
    assert "answered HTTP 307" in capsys.readouterr().err


def test_trace_push_reports_partial_success(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """An OTLP partial-success answer is accepted with a warning."""

    event_log = tmp_path / "runs.sqlite"
    _run(event_log, "partial", capsys)
    body = json.dumps({"partialSuccess": {"rejectedSpans": "1", "errorMessage": "span too large"}}).encode()

    with _otlp_stub(body=body) as stub:
        assert _trace("--event-log", str(event_log), "--otlp-endpoint", stub.url) == 0

    assert "warning: the OTLP receiver rejected 1 span(s): span too large" in capsys.readouterr().err


def test_trace_push_reports_unreachable_endpoints(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A refused connection is an export failure with exit code 1."""

    event_log = tmp_path / "runs.sqlite"
    _run(event_log, "offline", capsys)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]

    code = _trace("--event-log", str(event_log), "--otlp-endpoint", f"http://127.0.0.1:{port}/v1/traces?key=abc")
    error = capsys.readouterr().err

    assert code == 1
    assert f"cannot reach http://127.0.0.1:{port}/v1/traces: " in error
    assert "refused" in error.lower()
    assert "key=abc" not in error
    assert NOT_HTTP1_HINT not in error


@pytest.mark.parametrize(
    ("reply", "message", "hinted"),
    [
        # A gRPC server built on gRPC C-core answers an HTTP/1.1 request with HTTP/2 frames.
        (HTTP2_SETTINGS_FRAME, "{url} did not answer with HTTP/1.x", True),
        # grpc-go (Jaeger, OpenTelemetry Collector) reads the HTTP/2 preface, then resets the connection.
        (None, "{url} closed the connection without an HTTP/1.x answer", True),
        (b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\nzz\r\n", "the HTTP exchange with {url} failed", False),
        (b"HTTP/1.1 502 Bad Gateway\r\nTransfer-Encoding: chunked\r\n\r\nzz\r\n", "{url} answered HTTP 502", False),
    ],
    ids=["http2-frames", "connection-reset", "broken-200-body", "broken-502-body"],
)
def test_trace_push_reports_answers_that_are_not_http1(
    reply: bytes | None, message: str, hinted: bool, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A server that does not answer with valid HTTP/1.x is an export failure (exit 1), never a traceback."""

    event_log = tmp_path / "runs.sqlite"
    _run(event_log, "not-http1", capsys)

    with _raw_responder(reply) as url:
        code = _trace("--event-log", str(event_log), "--otlp-endpoint", url, "--otlp-header", f"X-Token={TOKEN}")
    error = capsys.readouterr().err

    assert code == 1
    assert f"error: OTLP export failed: {message.format(url=url)}" in error
    assert (NOT_HTTP1_HINT in error) is hinted
    assert TOKEN not in error


@pytest.mark.parametrize(
    ("endpoint", "message"),
    [
        ("https://user:s3cret-pw@otlp.example.com/v1/traces", "--otlp-endpoint must not contain credentials"),
        ("http://user:s3cret-pw@127.0.0.1:4318/v1/traces", "--otlp-endpoint must not contain credentials"),
        ("http://localhost:4318x/v1/traces", "--otlp-endpoint has an invalid port '4318x'"),
        ("http://localhost:99999/v1/traces", "--otlp-endpoint has an invalid port '99999'"),
        ("http://localhost:4318/v1/tr aces", "--otlp-endpoint must be percent-encoded"),
        ("http://localhost:4318/v1/trac\u00e9s", "--otlp-endpoint must be percent-encoded"),
    ],
    ids=["credentials", "credentials-and-port", "non-numeric-port", "port-out-of-range", "space", "non-ascii"],
)
def test_trace_rejects_endpoints_it_cannot_send_to(
    endpoint: str, message: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Endpoints urllib cannot send to are invalid arguments (exit 2); credentials are never printed."""

    event_log = tmp_path / "runs.sqlite"
    _run(event_log, "bad-endpoint", capsys)

    code = _trace("--event-log", str(event_log), "--otlp-endpoint", endpoint)
    captured = capsys.readouterr()

    assert code == 2
    assert f"error: {message}" in captured.err
    assert captured.out == ""
    assert "s3cret" not in captured.out + captured.err


def test_trace_push_reports_headers_http_cannot_carry(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A header value HTTP/1.1 cannot encode fails the export cleanly, without sending or printing it."""

    event_log = tmp_path / "runs.sqlite"
    _run(event_log, "header", capsys)
    team = "\u30c1\u30fc\u30e0"

    with _otlp_stub() as stub:
        code = _trace("--event-log", str(event_log), "--otlp-endpoint", stub.url, "--otlp-header", f"X-Team={team}")
    error = capsys.readouterr().err

    assert code == 1
    assert f"error: OTLP export failed: cannot send the request to {stub.url}" in error
    assert team not in error
    assert stub.received == []
