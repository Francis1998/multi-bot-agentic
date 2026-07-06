"""Tests for the JSON validation and canonicalization tool."""

from __future__ import annotations

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.json_format import JsonFormatTool


def _run(document: str) -> tuple[bool, str]:
    """Execute the json_format tool for a document.

    Args:
        document: JSON document text to validate.

    Returns:
        Tuple of ``(ok, content)`` from the tool result.
    """

    result = JsonFormatTool().execute(ToolInvocation(tool_name="json_format", arguments={"text": document}))
    return result.ok, result.content


def test_json_format_canonicalizes_object() -> None:
    """A valid object is re-serialized with sorted keys and indentation."""

    ok, content = _run('{"b": 1, "a": 2}')

    assert ok is True
    assert content == '{\n  "a": 2,\n  "b": 1\n}'


def test_json_format_rejects_invalid_json() -> None:
    """A malformed document returns a structured failure, not a crash."""

    ok, content = _run("{not valid json}")

    assert ok is False
    assert "invalid JSON" in content


def test_json_format_rejects_empty_document() -> None:
    """An empty document is reported as a failure."""

    ok, content = _run("   ")

    assert ok is False
    assert "empty" in content


def test_json_format_reports_top_level_type() -> None:
    """A JSON array's canonical form and top-level type are reported."""

    result = JsonFormatTool().execute(ToolInvocation(tool_name="json_format", arguments={"text": "[3, 1, 2]"}))

    assert result.ok is True
    assert result.content == "[\n  3,\n  1,\n  2\n]"
    assert result.metadata == {"top_level_type": "list"}
