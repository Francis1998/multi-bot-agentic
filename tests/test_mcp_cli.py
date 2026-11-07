"""CLI tests for ``mcp-tools`` and ``run --mcp-config``."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

import pytest

from multi_bot_agentic.checkpoint import save_checkpoint
from multi_bot_agentic.cli import build_parser, mcp_tools_command, replay_command, resume_command, run_command
from multi_bot_agentic.event_log import SQLiteEventLog
from multi_bot_agentic.models import Observation, RunState

FIXTURES = Path(__file__).parent / "fixtures" / "mcp"
EXAMPLE_CONFIG = Path(__file__).resolve().parents[1] / "examples" / "mcp" / "mcp.json"


def _write_config(tmp_path: Path, **extra_servers: dict[str, Any]) -> Path:
    servers: dict[str, Any] = {
        "modern": {"command": sys.executable, "args": [str(FIXTURES / "modern_server.py")], "deniedTools": ["crash"]},
        "legacy": {"command": sys.executable, "args": [str(FIXTURES / "legacy_server.py")]},
        **extra_servers,
    }
    path = tmp_path / "mcp.json"
    path.write_text(json.dumps({"mcpServers": servers}), encoding="utf-8")
    return path


def test_mcp_tools_lists_servers_eras_and_tools(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The text listing shows each server's era, protocol version, identity, and tool signatures."""

    args = build_parser().parse_args(["mcp-tools", "--mcp-config", str(_write_config(tmp_path))])

    assert mcp_tools_command(args) == 0
    out = capsys.readouterr().out
    assert "server modern: modern 2026-07-28 (modern-fixture/1.0.0), 10 tools, 1 hidden" in out
    assert "skipped: bad name:x" in out
    assert "server legacy: legacy 2025-11-25 (legacy-fixture/0.9.0), 4 tools" in out
    assert "  - mcp__legacy__shout(text: string (required))" in out
    assert "      [MCP legacy] Upper-case the text." in out


def test_mcp_tools_json_reports_failures_with_exit_code(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """JSON output is machine-readable and a broken server makes the command exit 1."""

    config = _write_config(tmp_path, broken={"command": str(tmp_path / "missing-server")})
    args = build_parser().parse_args(["mcp-tools", "--mcp-config", str(config), "--format", "json"])

    assert mcp_tools_command(args) == 1
    payload = json.loads(capsys.readouterr().out)
    by_name = {server["name"]: server for server in payload["servers"]}
    assert by_name["modern"]["era"] == "modern"
    assert by_name["legacy"]["protocol_version"] == "2025-11-25"
    assert "cannot start MCP server 'broken'" in by_name["broken"]["error"]
    shout = next(tool for tool in payload["tools"] if tool["name"] == "mcp__legacy__shout")
    assert shout["remote_name"] == "shout"
    assert shout["input_schema"]["required"] == ["text"]


def test_mcp_tools_rejects_invalid_config(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Config errors are reported on stderr with exit code 2 (no traceback)."""

    config = tmp_path / "bad.json"
    config.write_text(json.dumps({"mcpServers": {"a__b": {"command": "x"}}}), encoding="utf-8")

    assert mcp_tools_command(build_parser().parse_args(["mcp-tools", "--mcp-config", str(config)])) == 2
    assert "invalid MCP server name 'a__b'" in capsys.readouterr().err


def test_run_with_mcp_config_calls_tool_and_replay_shows_it(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``run --mcp-config`` exposes MCP tools; ``replay --format text`` shows the MCP call."""

    monkeypatch.setenv("MULTIBOT_FAKE_TOOL", "mcp__modern__echo")
    event_log = tmp_path / "runs.sqlite"
    parser = build_parser()
    run_args = parser.parse_args(
        [
            "run",
            "--goal",
            "summarize the MCP rollout",
            "--provider",
            "fake",
            "--max-steps",
            "5",
            "--event-log",
            str(event_log),
            "--run-id",
            "cli-mcp",
            "--mcp-config",
            str(_write_config(tmp_path)),
        ]
    )

    assert run_command(run_args) == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out)["state"] == "succeeded"
    assert "mcp: modern modern 2026-07-28 (10 tools)" in captured.err
    assert "mcp: legacy legacy 2025-11-25 (4 tools)" in captured.err

    replay_args = parser.parse_args(
        ["replay", "--event-log", str(event_log), "--run-id", "cli-mcp", "--format", "text"]
    )
    assert replay_command(replay_args) == 0
    timeline = capsys.readouterr().out
    assert "decision action=call_tool rule=model.requested-tool" in timeline
    assert "action_result kind=tool target=mcp__modern__echo ok=true mcp=modern/echo era=modern" in timeline


def test_resume_with_mcp_config_executes_a_pending_mcp_tool_request(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``resume --mcp-config`` re-attaches MCP tools so a checkpointed tool request can run."""

    event_log = tmp_path / "runs.sqlite"
    log = SQLiteEventLog(event_log)
    save_checkpoint(
        log,
        run_id="resume-mcp",
        goal="echo after resume",
        step=1,
        state=RunState.ACTING,
        observations=(
            Observation(source="user", content="echo after resume"),
            Observation(source="llm:fake", content="TOOL:mcp__legacy__shout:resumed via mcp"),
        ),
    )
    log.close()
    args = build_parser().parse_args(
        [
            "resume",
            "--run-id",
            "resume-mcp",
            "--event-log",
            str(event_log),
            "--provider",
            "fake",
            "--mcp-config",
            str(_write_config(tmp_path)),
        ]
    )

    assert resume_command(args) == 0
    assert json.loads(capsys.readouterr().out)["state"] == "succeeded"
    log = SQLiteEventLog(event_log)
    tool_results = [
        (event.payload["tool"], event.payload["content"])
        for event in log.list_events("resume-mcp")
        if event.event_type == "action_result" and event.payload.get("kind") == "tool"
    ]
    log.close()
    assert tool_results == [("mcp__legacy__shout", "RESUMED VIA MCP")]


def test_run_fails_fast_when_an_mcp_server_cannot_start(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A configured server that cannot start aborts the run before any provider call."""

    config = tmp_path / "mcp.json"
    config.write_text(json.dumps({"mcpServers": {"gone": {"command": str(tmp_path / "nope")}}}), encoding="utf-8")
    event_log = tmp_path / "runs.sqlite"
    args = build_parser().parse_args(
        ["run", "--goal", "g", "--provider", "fake", "--event-log", str(event_log), "--mcp-config", str(config)]
    )

    assert run_command(args) == 2
    assert "MCP server startup failed: gone: cannot start MCP server 'gone'" in capsys.readouterr().err
    assert not event_log.exists()


@pytest.mark.skipif(shutil.which("python3") is None, reason="example config launches python3 from PATH")
def test_example_config_lists_the_demo_notes_server(capsys: pytest.CaptureFixture[str]) -> None:
    """The shipped ``examples/mcp/mcp.json`` works as documented."""

    assert mcp_tools_command(build_parser().parse_args(["mcp-tools", "--mcp-config", str(EXAMPLE_CONFIG)])) == 0
    out = capsys.readouterr().out
    assert "server notes: modern 2026-07-28 (notes-demo/1.0.0), 2 tools" in out
    assert "  - mcp__notes__search_notes(query: string (required), limit: integer)" in out
