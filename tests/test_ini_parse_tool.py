"""Tests for the ini_parse tool."""

from __future__ import annotations

import json
from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.ini_parse import IniParseTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the ini_parse tool."""

    result = IniParseTool().execute(ToolInvocation(tool_name="ini_parse", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_ini_parse_sections_and_keys() -> None:
    """Valid INI text becomes sorted pretty JSON."""

    text = """
[database]
host = localhost
port = 5432

[cache]
ttl = 60
"""
    ok, content, metadata = _run(text=text)
    assert ok is True
    payload = json.loads(content)
    assert payload["database"]["host"] == "localhost"
    assert payload["database"]["port"] == "5432"
    assert payload["cache"]["ttl"] == "60"
    assert metadata["sections"] == 2
    assert metadata["keys"] == 3


def test_ini_parse_rejects_empty() -> None:
    """Empty text fails."""

    ok, content, metadata = _run(text="  ")
    assert ok is False
    assert "non-empty" in content
    assert metadata["chars"] == 2


def test_ini_parse_rejects_malformed() -> None:
    """Malformed INI with bad interpolation fails structurally."""

    ok, content, metadata = _run(text="[sec]\nkey = %(missing)s value")
    assert ok is False
    assert "ini parse error" in content
    assert "chars" in metadata


def test_ini_parse_rejects_oversized() -> None:
    """Text over 20_000 chars fails."""

    ok, content, metadata = _run(text="x" * 20_001)
    assert ok is False
    assert "exceeds max" in content
    assert metadata["chars"] == 20_001


def test_ini_parse_missing_argument() -> None:
    """Missing text fails."""

    ok, content, _metadata = _run()
    assert ok is False
    assert "missing required argument" in content


def test_ini_parse_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "ini_parse" in tools
    assert tools["ini_parse"].name == "ini_parse"
    SafetyPolicy().validate_tool("ini_parse")
    assert "ini_parse" in SafetyPolicy().allowed_tools
