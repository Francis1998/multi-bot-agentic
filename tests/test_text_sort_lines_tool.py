"""Tests for the deterministic text line-sorting tool."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.text_sort_lines import TextSortLinesTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the text_sort_lines tool with the given arguments.

    Args:
        **arguments: Tool arguments (``text``, optional ``order`` / ``unique``).

    Returns:
        Tuple of ``(ok, content, metadata)`` from the tool result.
    """

    result = TextSortLinesTool().execute(ToolInvocation(tool_name="text_sort_lines", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_text_sort_lines_defaults_to_ascending() -> None:
    """Without an order argument the tool sorts lines ascending."""

    ok, content, metadata = _run(text="cherry\napple\nbanana")

    assert ok is True
    assert content == "apple\nbanana\ncherry"
    assert metadata["order"] == "asc"
    assert metadata["unique"] is False
    assert metadata["lines"] == 3
    assert metadata["original_lines"] == 3


def test_text_sort_lines_descending() -> None:
    """A descending order argument reverses the lexicographic sort."""

    ok, content, metadata = _run(text="cherry\napple\nbanana", order="DESC")

    assert ok is True
    assert content == "cherry\nbanana\napple"
    assert metadata["order"] == "desc"


def test_text_sort_lines_unique_dedupes_after_sort() -> None:
    """``unique=true`` drops duplicate lines after sorting."""

    ok, content, metadata = _run(text="b\na\nb\nc\na", unique=True)

    assert ok is True
    assert content == "a\nb\nc"
    assert metadata["unique"] is True
    assert metadata["lines"] == 3
    assert metadata["original_lines"] == 5


def test_text_sort_lines_accepts_string_unique() -> None:
    """String boolean-like ``unique`` values are accepted."""

    ok, content, metadata = _run(text="z\ny\nz", unique="yes")

    assert ok is True
    assert content == "y\nz"
    assert metadata["unique"] is True


def test_text_sort_lines_rejects_empty_text() -> None:
    """Empty text is a structured failure."""

    ok, content, _metadata = _run(text="")

    assert ok is False
    assert "empty" in content


def test_text_sort_lines_rejects_oversized_text() -> None:
    """Documents above the character cap return a structured failure."""

    ok, content, metadata = _run(text="x" * 20_001)

    assert ok is False
    assert "max_chars" in content
    assert metadata["chars"] == 20_001


def test_text_sort_lines_rejects_unknown_order() -> None:
    """An unsupported order returns a structured failure, not a crash."""

    ok, content, _metadata = _run(text="a\nb", order="random")

    assert ok is False
    assert "unsupported order" in content


def test_text_sort_lines_rejects_invalid_unique() -> None:
    """A non-boolean ``unique`` value is a structured failure."""

    ok, content, _metadata = _run(text="a\nb", unique="maybe")

    assert ok is False
    assert "unique must be a boolean" in content


def test_text_sort_lines_is_registered_in_default_tools() -> None:
    """The text_sort_lines tool is wired into the default allowlisted registry."""

    tools = build_default_tools(root=Path.cwd())
    assert "text_sort_lines" in tools
    assert tools["text_sort_lines"].name == "text_sort_lines"
    assert "text_sort_lines" in SafetyPolicy().allowed_tools
