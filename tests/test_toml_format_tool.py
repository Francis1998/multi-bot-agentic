"""Tests for the TOML validation and canonicalization tool."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.toml_format import TomlFormatTool


def _run(document: str) -> tuple[bool, str]:
    """Execute the toml_format tool for a document.

    Args:
        document: TOML document text to validate.

    Returns:
        Tuple of ``(ok, content)`` from the tool result.
    """

    result = TomlFormatTool().execute(ToolInvocation(tool_name="toml_format", arguments={"text": document}))
    return result.ok, result.content


def test_toml_format_canonicalizes_document() -> None:
    """A valid document is re-serialized with sorted keys and stable tables."""

    ok, content = _run(
        """
b = 1
[models]
names = ["Kimi K2", "Claude Sonnet 4.6"]
[a]
z = true
retries = 2
"""
    )

    assert ok is True
    assert content == "\n".join(
        [
            "b = 1",
            "",
            "[a]",
            "retries = 2",
            "z = true",
            "",
            "[models]",
            'names = ["Kimi K2", "Claude Sonnet 4.6"]',
        ]
    )


def test_toml_format_rejects_invalid_toml() -> None:
    """Malformed TOML returns a structured failure, not a crash."""

    ok, content = _run("models = [GPT-5.5, Kimi K2")

    assert ok is False
    assert "invalid TOML" in content


def test_toml_format_rejects_empty_document() -> None:
    """An empty document is reported as a failure."""

    ok, content = _run("   ")

    assert ok is False
    assert "empty" in content


def test_toml_format_rejects_oversized_document() -> None:
    """Documents above the fixed character cap are refused before parsing."""

    ok, content = _run("text = " + ('"' + ("x" * 20_001) + '"'))

    assert ok is False
    assert "max_chars=20000" in content


def test_toml_format_rejects_datetime_values() -> None:
    """Offset date-time values are outside the portable scalar subset."""

    ok, content = _run("released = 2026-07-28T12:00:00Z")

    assert ok is False
    assert "invalid TOML" in content
    assert "unsupported" in content


def test_toml_format_reports_metadata() -> None:
    """Successful results include top-level type and key count."""

    result = TomlFormatTool().execute(
        ToolInvocation(
            tool_name="toml_format",
            arguments={"text": 'enabled = true\nmodels = ["GPT-5.5", "Gemini 3.x"]\n'},
        )
    )

    assert result.ok is True
    assert "enabled = true" in result.content
    assert result.metadata == {"top_level_type": "dict", "keys": 2}


def test_toml_format_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is available through the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "toml_format" in tools
    assert tools["toml_format"].name == "toml_format"
    SafetyPolicy().validate_tool("toml_format")
    assert "toml_format" in SafetyPolicy().allowed_tools
