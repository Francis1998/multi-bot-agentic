"""Tests for the dual-era stdio MCP client against fake modern/legacy servers."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any

import pytest

from multi_bot_agentic.mcp.client import (
    McpEra,
    McpProtocolError,
    McpTimeoutError,
    McpTransportError,
    McpVersionError,
    StdioMcpClient,
)

FIXTURES = Path(__file__).parent / "fixtures" / "mcp"
MODERN = (sys.executable, str(FIXTURES / "modern_server.py"))
LEGACY = (sys.executable, str(FIXTURES / "legacy_server.py"))


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _wait_dead(pid: int, timeout: float = 3.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _alive(pid):
            return True
        time.sleep(0.02)
    return False


def test_modern_server_is_detected_with_server_discover() -> None:
    """A DiscoverResult selects the modern era; tools/list follows pagination in order."""

    with StdioMcpClient(MODERN, name="modern") as client:
        tools = client.list_tools()
        assert client.era is McpEra.MODERN
        assert client.protocol_version == "2026-07-28"
        assert client.server_info == {"name": "modern-fixture", "version": "1.0.0"}
        assert client.instructions == "Modern fixture for tests."

    names = [tool.name for tool in tools]
    assert names[:4] == ["echo", "add", "fail", "sleep"]
    assert len(names) == 9
    assert tools[0].input_schema["required"] == ["text"]


def test_legacy_server_falls_back_to_initialize_on_probe_error() -> None:
    """A non-modern probe error (-32601) triggers the legacy initialize handshake."""

    started = time.monotonic()
    with StdioMcpClient(LEGACY, name="legacy") as client:
        result = client.call_tool("shout", {"text": "hello"})
        assert client.era is McpEra.LEGACY
        assert client.protocol_version == "2025-11-25"
        assert client.server_info["name"] == "legacy-fixture"

    assert result.content == ({"type": "text", "text": "HELLO"},)
    assert time.monotonic() - started < 3.0


def test_legacy_server_falls_back_after_probe_timeout() -> None:
    """A legacy server that ignores the probe is detected once the probe times out."""

    command = (*LEGACY, "--silent-probe")
    with StdioMcpClient(command, name="silent", probe_timeout_seconds=0.3) as client:
        assert client.era is McpEra.LEGACY
        assert [tool.name for tool in client.list_tools()] == ["echo", "shout", "fail", "ping_client"]


def test_legacy_negotiation_accepts_2025_06_18() -> None:
    """The client accepts an older legacy revision chosen by the server."""

    with StdioMcpClient((*LEGACY, "--versions", "2025-06-18"), name="old") as client:
        assert client.protocol_version == "2025-06-18"
        assert client.call_tool("echo", {"text": "ok"}).content[0]["text"] == "ok"


def test_unsupported_version_error_retries_with_mutual_version() -> None:
    """-32022 identifies a modern server; the client retries instead of falling back."""

    client = StdioMcpClient(MODERN, name="retry", modern_versions=("2099-01-01", "2026-07-28"))
    with client:
        assert client.era is McpEra.MODERN
        assert client.protocol_version == "2026-07-28"


def test_no_mutual_version_raises_and_cleans_up() -> None:
    """Without a shared version the client fails fast instead of falling back to initialize."""

    client = StdioMcpClient(MODERN, name="future", modern_versions=("2099-01-01",))
    with pytest.raises(McpVersionError, match="supports"):
        client.start()
    assert client.pid is None


def test_slow_modern_server_is_recovered_from_late_probe_answer() -> None:
    """A probe answered after the timeout still selects the modern era when initialize is rejected."""

    command = (*MODERN, "--slow-start", "0.8")
    with StdioMcpClient(command, name="slow", probe_timeout_seconds=0.2) as client:
        assert client.era is McpEra.MODERN
        assert client.call_tool("echo", {"text": "late"}).content[0]["text"] == "late"


def test_era_is_cached_for_the_server_process(monkeypatch: pytest.MonkeyPatch) -> None:
    """Only the first request probes; later requests reuse the cached era."""

    client = StdioMcpClient(MODERN, name="cache")
    methods: list[str] = []
    original = client._issue

    def spy(method: str, params: dict[str, Any], deadline: float) -> int:
        methods.append(method)
        return original(method, params, deadline)

    monkeypatch.setattr(client, "_issue", spy)
    with client:
        client.list_tools()
        client.call_tool("echo", {"text": "one"})
        client.call_tool("echo", {"text": "two"})

    assert methods.count("server/discover") == 1
    assert "initialize" not in methods


def test_call_tool_reports_is_error_and_protocol_errors() -> None:
    """``isError`` stays a result; JSON-RPC errors raise ``McpProtocolError``."""

    with StdioMcpClient(MODERN, name="errors") as client:
        failed = client.call_tool("fail", {"reason": "bad input"})
        added = client.call_tool("add", {"a": 2, "b": 3})
        with pytest.raises(McpProtocolError) as excinfo:
            client.call_tool("ghost", {})

    assert failed.is_error
    assert failed.content[0]["text"] == "tool failed: bad input"
    assert added.structured_content == {"sum": 5}
    assert excinfo.value.code == -32602


def test_call_timeout_does_not_hang_and_server_stays_usable() -> None:
    """A slow tool times out on schedule; the next call still works."""

    with StdioMcpClient(MODERN, name="slowtool") as client:
        started = time.monotonic()
        with pytest.raises(McpTimeoutError, match=r"did not answer tools/call within 0\.2s"):
            client.call_tool("sleep", {"seconds": 0.8}, timeout_seconds=0.2)
        assert time.monotonic() - started < 0.6
        assert client.call_tool("echo", {"text": "still here"}, timeout_seconds=5).content[0]["text"] == "still here"


def test_crashed_server_is_restarted_within_budget() -> None:
    """An unexpected exit is reported, restarted once, then the budget is enforced."""

    with StdioMcpClient(MODERN, name="crashy", max_restarts=1) as client:
        first_pid = client.pid
        with pytest.raises(McpTransportError, match="closed its stdout"):
            client.call_tool("crash", {})
        assert client.call_tool("echo", {"text": "back"}).content[0]["text"] == "back"
        assert client.pid != first_pid
        with pytest.raises(McpTransportError):
            client.call_tool("crash", {})
        with pytest.raises(McpTransportError, match="unavailable"):
            client.call_tool("echo", {"text": "no more restarts"})


def test_close_terminates_the_server_and_rejects_new_calls() -> None:
    """``close`` stops the process; the client cannot be reused afterwards."""

    client = StdioMcpClient(MODERN, name="closing")
    client.start()
    pid = client.pid
    assert pid is not None
    client.close()

    assert _wait_dead(pid)
    with pytest.raises(McpTransportError, match="is closed"):
        client.call_tool("echo", {"text": "x"})


def test_unanswering_server_times_out_and_is_killed() -> None:
    """A server that never answers cannot hang startup, and its process is cleaned up."""

    hung = (sys.executable, "-c", "import time; time.sleep(60)")
    client = StdioMcpClient(hung, name="hung", startup_timeout_seconds=0.6, probe_timeout_seconds=0.2)
    started = time.monotonic()
    with pytest.raises(McpTimeoutError, match="answered neither server/discover nor initialize"):
        client.start()

    assert time.monotonic() - started < 5.0
    assert client.pid is None


def test_missing_executable_raises_transport_error(tmp_path: Path) -> None:
    """A bad command surfaces as ``McpTransportError`` instead of ``FileNotFoundError``."""

    client = StdioMcpClient((str(tmp_path / "no-such-server"),), name="missing")
    with pytest.raises(McpTransportError, match="cannot start MCP server 'missing'"):
        client.start()


def test_server_exiting_during_startup_is_a_transport_error() -> None:
    """A server that exits before answering fails fast with a transport error."""

    dying = (sys.executable, "-c", "import sys; print('boom', file=sys.stderr); sys.exit(4)")
    client = StdioMcpClient(dying, name="dying", startup_timeout_seconds=5.0)
    started = time.monotonic()
    with pytest.raises(McpTransportError, match="MCP server 'dying'"):
        client.start()
    assert time.monotonic() - started < 3.0


def test_legacy_server_ping_is_answered() -> None:
    """Legacy servers may ping the client mid-request; the client answers."""

    with StdioMcpClient(LEGACY, name="pinger") as client:
        result = client.call_tool("ping_client", {})

    assert result.content[0]["text"] == "client answered ping"


def test_writes_to_a_server_that_stops_reading_stdin_time_out() -> None:
    """A full stdin pipe cannot hang a call, and close() still returns promptly."""

    client = StdioMcpClient(MODERN, name="backpressure", max_restarts=0)
    client.start()
    with pytest.raises(McpTimeoutError):
        client.call_tool("sleep", {"seconds": 6}, timeout_seconds=0.2)
    started = time.monotonic()
    with pytest.raises(McpTimeoutError):
        client.call_tool("echo", {"text": "x" * 1_000_000}, timeout_seconds=0.5)
    assert time.monotonic() - started < 2.0
    started = time.monotonic()
    client.close()
    assert time.monotonic() - started < 4.0


def test_close_kills_children_that_outlive_the_launcher(tmp_path: Path) -> None:
    """Process-group cleanup also reaches children that ignore SIGTERM after the launcher exits."""

    pid_file = tmp_path / "child.pid"
    client = StdioMcpClient((*MODERN, "--spawn-child", str(pid_file)), name="spawner")
    client.start()
    deadline = time.monotonic() + 5.0
    while not pid_file.exists() or not pid_file.read_text():
        assert time.monotonic() < deadline, "child never started"
        time.sleep(0.02)
    child_pid = int(pid_file.read_text())
    assert _alive(child_pid)

    client.close()

    assert _wait_dead(child_pid, timeout=5.0)
