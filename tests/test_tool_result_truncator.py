"""Tests for ToolResultTruncator."""

from __future__ import annotations

import pytest

from multi_bot_agentic.tool_result_truncator import ToolResultTruncator


def test_passthrough_when_under_budget() -> None:
    """Short strings are returned unchanged."""

    text = "ok result"
    result = ToolResultTruncator().truncate(text, max_chars=100)
    assert result.text == text
    assert result.was_truncated is False
    assert result.original_len == len(text)
    assert result.truncated_len == len(text)
    assert result.marker == ""


def test_mid_string_truncate_with_marker() -> None:
    """Oversized text is soft-truncated mid-string with the ellipsis marker."""

    text = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    marker = "…"
    result = ToolResultTruncator(marker=marker).truncate(text, max_chars=11)
    assert result.was_truncated is True
    assert result.marker == marker
    assert marker in result.text
    assert result.truncated_len == 11
    assert result.truncated_len <= 11
    assert result.original_len == len(text)
    assert result.text.startswith("A")
    assert result.text.endswith("Z")


def test_never_empty_when_input_nonempty_and_budget_ge_one() -> None:
    """Non-empty input with max_chars >= 1 never yields empty text."""

    text = "tool-output-payload"
    for budget in (1, 2, 3, 5, 8):
        result = ToolResultTruncator(marker="…[truncated]…").truncate(text, max_chars=budget)
        assert result.text, f"empty at budget={budget}"
        assert len(result.text) <= budget
        assert result.was_truncated is True


def test_max_chars_zero_returns_empty() -> None:
    """max_chars=0 yields empty text and marks truncation when input non-empty."""

    result = ToolResultTruncator().truncate("hello", max_chars=0)
    assert result.text == ""
    assert result.was_truncated is True
    assert result.truncated_len == 0


def test_custom_marker() -> None:
    """Caller-supplied marker is embedded when truncating."""

    marker = "<<<CUT>>>"
    text = "0123456789" * 5
    result = ToolResultTruncator(marker=marker).truncate(text, max_chars=30)
    assert result.was_truncated is True
    assert marker in result.text
    assert result.marker == marker
    assert len(result.text) == 30


def test_rejects_negative_max_chars() -> None:
    """Negative max_chars raises ValueError."""

    with pytest.raises(ValueError, match="max_chars"):
        ToolResultTruncator().truncate("x", max_chars=-1)


def test_rejects_non_string() -> None:
    """Non-string input raises TypeError."""

    with pytest.raises(TypeError):
        ToolResultTruncator().truncate(123, max_chars=10)  # type: ignore[arg-type]


def test_empty_marker_rejected() -> None:
    """Empty marker is rejected at construction."""

    with pytest.raises(ValueError, match="marker"):
        ToolResultTruncator(marker="")
