"""Tests for the line-number annotation tool."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.line_number import LineNumberTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the line_number tool with the given arguments."""

    result = LineNumberTool().execute(ToolInvocation(tool_name="line_number", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_line_number_annotates_lines() -> None:
    """Lines receive padded 1-based prefixes by default."""

    ok, content, metadata = _run(text="alpha\nbeta\ngamma\n")

    assert ok is True
    assert content == "1| alpha\n2| beta\n3| gamma\n"
    assert cast(int, metadata["lines"]) == 3
    assert metadata["start"] == 1


def test_line_number_respects_start_and_separator() -> None:
    """Custom start and separator are applied."""

    ok, content, metadata = _run(text="a\nb", start=10, separator=": ")

    assert ok is True
    assert content == "10: a\n11: b"
    assert metadata["start"] == 10


def test_line_number_rejects_empty_text() -> None:
    """Empty input is a structured failure."""

    ok, content, _metadata = _run(text="   ")

    assert ok is False
    assert "empty" in content


def test_line_number_rejects_oversized_text() -> None:
    """Documents above the char cap are refused."""

    ok, content, metadata = _run(text="x" * 20_001)

    assert ok is False
    assert "max_chars" in content
    assert metadata["chars"] == 20_001


def test_line_number_rejects_negative_start() -> None:
    """Negative start values are refused."""

    ok, content, metadata = _run(text="a", start=-1)

    assert ok is False
    assert "start must be >= 0" in content
    assert metadata["start"] == -1


def test_line_number_rejects_newline_separator() -> None:
    """Separators containing newlines are refused."""

    ok, content, _metadata = _run(text="a", separator="|\n")

    assert ok is False
    assert "separator" in content


def test_line_number_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "line_number" in tools
    assert tools["line_number"].name == "line_number"
    SafetyPolicy().validate_tool("line_number")
    assert "line_number" in SafetyPolicy().allowed_tools
