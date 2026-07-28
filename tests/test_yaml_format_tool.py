"""Tests for the YAML validation and canonicalization tool."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.yaml_format import YamlFormatTool


def _run(document: str) -> tuple[bool, str]:
    """Execute the yaml_format tool for a document.

    Args:
        document: YAML document text to validate.

    Returns:
        Tuple of ``(ok, content)`` from the tool result.
    """

    result = YamlFormatTool().execute(ToolInvocation(tool_name="yaml_format", arguments={"text": document}))
    return result.ok, result.content


def test_yaml_format_canonicalizes_supported_subset() -> None:
    """A valid subset document is sorted and re-indented deterministically."""

    ok, content = _run(
        """
b: 1
models:
    - Kimi K2
    - Claude Sonnet 4.6
a:
  z: true
  retries: 2
"""
    )

    assert ok is True
    assert content == "\n".join(
        [
            "a:",
            "  retries: 2",
            "  z: true",
            "b: 1",
            "models:",
            "  - Kimi K2",
            "  - Claude Sonnet 4.6",
        ]
    )


def test_yaml_format_rejects_invalid_yaml() -> None:
    """Malformed subset syntax returns a structured failure, not a crash."""

    ok, content = _run("models: [GPT-5.5, Kimi K2")

    assert ok is False
    assert "invalid YAML" in content


def test_yaml_format_rejects_empty_document() -> None:
    """An empty document is reported as a failure."""

    ok, content = _run("   ")

    assert ok is False
    assert "empty" in content


def test_yaml_format_rejects_oversized_document() -> None:
    """Documents above the fixed character cap are refused before parsing."""

    ok, content = _run("text: " + ("x" * 20_001))

    assert ok is False
    assert "max_chars=20000" in content


def test_yaml_format_reports_top_level_type() -> None:
    """Successful results include the parsed top-level type."""

    result = YamlFormatTool().execute(
        ToolInvocation(tool_name="yaml_format", arguments={"text": '{"b": 1, "a": [true, null]}'})
    )

    assert result.ok is True
    assert result.content == "\n".join(
        [
            "a:",
            "  - true",
            "  - null",
            "b: 1",
        ]
    )
    assert result.metadata == {"top_level_type": "dict"}


def test_yaml_format_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is available through the default registry and safety allowlist."""

    assert "yaml_format" in build_default_tools(tmp_path)
    SafetyPolicy().validate_tool("yaml_format")
