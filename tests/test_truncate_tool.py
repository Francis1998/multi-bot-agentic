"""Tests for the deterministic text truncation tool."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.text_truncate import TextTruncateTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the truncate tool with the given arguments.

    Args:
        **arguments: Tool arguments (``text``, optional ``max_length`` / ``ellipsis``).

    Returns:
        Tuple of ``(ok, content, metadata)`` from the tool result.
    """

    result = TextTruncateTool().execute(ToolInvocation(tool_name="truncate", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_truncate_clips_with_default_ellipsis() -> None:
    """Text longer than ``max_length`` is clipped and ends with ``...``."""

    ok, content, metadata = _run(text="abcdefghij", max_length=7)

    assert ok is True
    assert content == "abcd..."
    assert len(content) == 7
    assert metadata["truncated"] is True
    assert metadata["ellipsis_applied"] is True
    assert metadata["original_chars"] == 10


def test_truncate_leaves_short_text_unchanged() -> None:
    """Text already within the limit is returned verbatim."""

    ok, content, metadata = _run(text="short", max_length=10)

    assert ok is True
    assert content == "short"
    assert metadata["truncated"] is False


def test_truncate_accepts_sentinel_max_length() -> None:
    """A ``<<<TRUNCATE>>>`` sentinel embeds max_length in the single text payload."""

    ok, content, metadata = _run(text="abcdefghij<<<TRUNCATE>>>7")

    assert ok is True
    assert content == "abcd..."
    assert metadata["truncated"] is True
    assert metadata["max_length"] == 7


def test_truncate_custom_ellipsis() -> None:
    """A custom ellipsis marker is appended when clipping."""

    ok, content, metadata = _run(text="abcdefghij", max_length=6, ellipsis="…")

    assert ok is True
    assert content == "abcde…"
    assert metadata["truncated"] is True


def test_truncate_rejects_empty_text() -> None:
    """Empty text is a structured failure."""

    ok, content, _metadata = _run(text="", max_length=5)

    assert ok is False
    assert "empty" in content


def test_truncate_is_registered_in_default_tools() -> None:
    """The truncate tool is wired into the default allowlisted registry."""

    tools = build_default_tools(root=Path.cwd())
    assert "truncate" in tools
    assert tools["truncate"].name == "truncate"
    assert "truncate" in SafetyPolicy().allowed_tools
