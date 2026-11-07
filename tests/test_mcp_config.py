"""Tests for the Claude-Desktop-compatible MCP config loader."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from multi_bot_agentic.mcp.config import (
    DEFAULT_CALL_TIMEOUT_SECONDS,
    DEFAULT_MAX_RESULT_BYTES,
    McpConfigError,
    McpServerConfig,
    load_mcp_config,
    parse_mcp_config,
)


def _parse(servers: dict[str, Any], environ: dict[str, str] | None = None) -> Any:
    return parse_mcp_config({"mcpServers": servers}, base_dir=Path("/configs"), environ=environ or {})


def test_parses_claude_desktop_entry_with_safety_options() -> None:
    """Standard command/args/env plus per-server safety keys are parsed."""

    config = _parse(
        {
            "notes": {
                "command": "python3",
                "args": ["server.py", "--verbose"],
                "env": {"NOTES_DIR": "/data"},
                "cwd": "servers",
                "allowedTools": ["search_*"],
                "deniedTools": ["search_private"],
                "callTimeoutSeconds": 5,
                "startupTimeoutSeconds": 12.5,
                "maxResultBytes": 2048,
                "redactResults": True,
            },
            "plain": {"command": "node", "args": ["index.js"]},
        }
    )

    notes, plain = config.servers
    assert notes == McpServerConfig(
        name="notes",
        command="python3",
        args=("server.py", "--verbose"),
        env={"NOTES_DIR": "/data"},
        cwd=Path("/configs/servers"),
        allowed_tools=("search_*",),
        denied_tools=("search_private",),
        call_timeout_seconds=5.0,
        startup_timeout_seconds=12.5,
        max_result_bytes=2048,
        redact_results=True,
    )
    assert plain.allowed_tools is None
    assert plain.call_timeout_seconds == DEFAULT_CALL_TIMEOUT_SECONDS
    assert plain.max_result_bytes == DEFAULT_MAX_RESULT_BYTES
    assert config.warnings == ()


def test_expands_environment_placeholders() -> None:
    """``${VAR}`` and ``${VAR:-default}`` expand; unset variables without defaults fail."""

    config = _parse(
        {
            "gh": {
                "command": "${TOOLS_BIN}/server",
                "args": ["--root", "${ROOT:-.}"],
                "env": {"GITHUB_TOKEN": "${GITHUB_TOKEN}"},
            }
        },
        environ={"TOOLS_BIN": "/opt/bin", "GITHUB_TOKEN": "ghp_secret"},
    )

    server = config.servers[0]
    assert server.command == "/opt/bin/server"
    assert server.args == ("--root", ".")
    assert server.env == {"GITHUB_TOKEN": "ghp_secret"}
    with pytest.raises(McpConfigError, match="GITHUB_TOKEN is not set"):
        _parse({"gh": {"command": "server", "env": {"GITHUB_TOKEN": "${GITHUB_TOKEN}"}}})


@pytest.mark.parametrize("name", ["a__b", "bad name", "trailing_", "-lead", "x" * 65, ""])
def test_rejects_server_names_that_break_namespacing(name: str) -> None:
    """Server names must keep ``mcp__<server>__<tool>`` unambiguous."""

    with pytest.raises(McpConfigError, match="invalid MCP server name"):
        _parse({name: {"command": "server"}})


def test_skips_remote_servers_and_warns_about_unknown_keys() -> None:
    """Remote entries are skipped and typos in keys are surfaced as warnings."""

    config = _parse(
        {
            "remote": {"type": "http", "url": "https://example.com/mcp"},
            "local": {"command": "server", "allowedTool": ["oops"]},
        }
    )

    assert [server.name for server in config.servers] == ["local"]
    assert config.servers[0].allowed_tools is None
    assert config.warnings == (
        "MCP server 'remote': only stdio servers are supported; skipping type='http'",
        "MCP server 'local': ignoring unknown key(s): allowedTool",
    )


@pytest.mark.parametrize(
    ("entry", "message"),
    [
        ({}, "'command' must be a non-empty string"),
        ({"command": "s", "args": "x"}, "'args' must be a list of strings"),
        ({"command": "s", "env": {"A": 1}}, "'env' must map strings to strings"),
        ({"command": "s", "callTimeoutSeconds": 0}, "'callTimeoutSeconds' must be a positive number"),
        ({"command": "s", "callTimeoutSeconds": float("nan")}, "'callTimeoutSeconds' must be a positive number"),
        ({"command": "s", "startupTimeoutSeconds": float("inf")}, "'startupTimeoutSeconds' must be a positive"),
        ({"command": "s", "callTimeoutSeconds": True}, "'callTimeoutSeconds' must be a positive number"),
        ({"command": "s", "maxResultBytes": 10.5}, "'maxResultBytes' must be a positive integer"),
        ({"command": "s", "allowedTools": "echo"}, "'allowedTools' must be a list of non-empty strings"),
        ({"command": "s", "disabled": "yes"}, "'disabled' must be true or false"),
    ],
)
def test_rejects_invalid_values(entry: dict[str, Any], message: str) -> None:
    """Every safety option is type-checked so a typo cannot silently disable it."""

    with pytest.raises(McpConfigError, match=message):
        _parse({"srv": entry})


def test_allow_and_deny_globs_with_deny_winning() -> None:
    """``deniedTools`` wins over ``allowedTools``; both accept glob patterns."""

    server = McpServerConfig(name="fs", command="x", allowed_tools=("read_*", "list_*"), denied_tools=("*_secret",))
    assert server.exposes("read_file")
    assert server.exposes("list_directory")
    assert not server.exposes("write_file")
    assert not server.exposes("read_secret")
    assert McpServerConfig(name="fs", command="x", denied_tools=("delete_*",)).exposes("anything")


def test_process_env_inherits_only_an_allowlist() -> None:
    """Provider API keys never reach MCP servers unless the config passes them explicitly."""

    server = McpServerConfig(name="s", command="x", env={"TOKEN": "explicit", "PATH": "/custom"})
    env = server.process_env({"PATH": "/usr/bin", "HOME": "/home/me", "OPENAI_API_KEY": "sk-leak", "TOKEN": "parent"})

    assert env == {"PATH": "/custom", "HOME": "/home/me", "TOKEN": "explicit"}


def test_load_reports_missing_and_malformed_files(tmp_path: Path) -> None:
    """File errors become ``McpConfigError`` with the path in the message."""

    with pytest.raises(McpConfigError, match="cannot read MCP config"):
        load_mcp_config(tmp_path / "missing.json")
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    with pytest.raises(McpConfigError, match="is not valid JSON"):
        load_mcp_config(broken)
    wrong_shape = tmp_path / "wrong.json"
    wrong_shape.write_text(json.dumps({"servers": []}), encoding="utf-8")
    with pytest.raises(McpConfigError, match="'mcpServers' object"):
        load_mcp_config(wrong_shape)


def test_load_resolves_cwd_against_config_dir_and_accepts_servers_alias(tmp_path: Path) -> None:
    """A relative ``cwd`` is anchored at the config file; VS Code's ``servers`` key is accepted."""

    path = tmp_path / "mcp.json"
    path.write_text(json.dumps({"servers": {"demo": {"command": "python3", "cwd": "."}}}), encoding="utf-8")

    config = load_mcp_config(path)

    assert config.source == path
    assert config.servers[0].cwd == tmp_path.resolve() / "."
    assert config.enabled_servers == config.servers


def test_load_rejects_non_utf8_files(tmp_path: Path) -> None:
    """A UTF-16 config is reported as an invalid config instead of a traceback."""

    path = tmp_path / "utf16.json"
    path.write_text(json.dumps({"mcpServers": {}}), encoding="utf-16")

    with pytest.raises(McpConfigError, match="not UTF-8"):
        load_mcp_config(path)
