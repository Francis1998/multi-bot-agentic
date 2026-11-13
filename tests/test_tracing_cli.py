"""CLI tests for ``trace``: formats, run selection, errors, and the OTLP/HTTP push."""

from __future__ import annotations

import json
import socket
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

    code = _trace(
        "--event-log", str(event_log), "--otlp-endpoint", f"http://user:pw@127.0.0.1:{port}/v1/traces?key=abc"
    )
    error = capsys.readouterr().err

    assert code == 1
    assert f"cannot reach http://127.0.0.1:{port}/v1/traces" in error
    assert "pw@" not in error and "key=abc" not in error
