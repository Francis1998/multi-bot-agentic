"""Tests for the deterministic unified-diff tool."""

from __future__ import annotations

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.tools.diff_text import DiffTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the diff tool with the given arguments.

    Args:
        **arguments: Tool arguments (``text``, optional ``other`` / ``context``).

    Returns:
        Tuple of ``(ok, content, metadata)`` from the tool result.
    """

    result = DiffTool().execute(ToolInvocation(tool_name="diff", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_diff_produces_unified_hunks() -> None:
    """Two differing sides yield a unified diff with added/removed counts."""

    ok, content, metadata = _run(text="alpha\nbeta\n", other="alpha\ngamma\n")

    assert ok is True
    assert "--- a" in content
    assert "+++ b" in content
    assert "-beta" in content
    assert "+gamma" in content
    assert metadata["added"] == 1
    assert metadata["removed"] == 1
    assert metadata["identical"] is False


def test_diff_identical_texts_yield_empty_content() -> None:
    """Identical sides succeed with empty content and ``identical=True``."""

    ok, content, metadata = _run(text="same\n", other="same\n")

    assert ok is True
    assert content == ""
    assert metadata["identical"] is True
    assert metadata["added"] == 0
    assert metadata["removed"] == 0


def test_diff_accepts_sentinel_split_in_text() -> None:
    """A single ``text`` split on ``<<<DIFF>>>`` supplies both sides."""

    ok, content, metadata = _run(text="one\n<<<DIFF>>>\ntwo\n")

    assert ok is True
    assert "-one" in content
    assert "+two" in content
    assert metadata["identical"] is False


def test_diff_rejects_missing_other_without_sentinel() -> None:
    """Without ``other`` or the sentinel, the tool returns a structured failure."""

    ok, content, _metadata = _run(text="only-one-side")

    assert ok is False
    assert "<<<DIFF>>>" in content


def test_diff_rejects_empty_side() -> None:
    """An empty right side is a structured failure."""

    ok, content, _metadata = _run(text="left", other="")

    assert ok is False
    assert "right text is empty" in content


def test_diff_rejects_oversized_side() -> None:
    """A side above the char cap is a structured failure."""

    ok, content, metadata = _run(text="x" * 20_001, other="y")

    assert ok is False
    assert "max_chars" in content
    assert metadata["chars"] == 20_001


def test_diff_rejects_invalid_context() -> None:
    """A non-integer or out-of-range ``context`` is a structured failure."""

    ok, content, _metadata = _run(text="a", other="b", context=-1)

    assert ok is False
    assert "context" in content


def test_diff_is_registered_in_default_tools() -> None:
    """The diff tool is wired into the default allowlisted registry."""

    from pathlib import Path

    tools = build_default_tools(root=Path.cwd())
    assert "diff" in tools
    assert tools["diff"].name == "diff"
