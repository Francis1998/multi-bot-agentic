"""Tests for ToolCallQuotaGuard."""

from __future__ import annotations

import pytest

from multi_bot_agentic.tool_call_quota import ToolCallQuotaGuard


def test_record_increments_until_exhausted() -> None:
    """Calls increment and exhausted flips at max_calls."""

    guard = ToolCallQuotaGuard(max_calls=3, mode="advisory")
    s1 = guard.record("sess-1", "search")
    assert s1.call_count == 1
    assert s1.remaining == 2
    assert s1.exhausted is False
    assert s1.allowed is True
    guard.record("sess-1", "search")
    s3 = guard.record("sess-1", "search")
    assert s3.call_count == 3
    assert s3.remaining == 0
    assert s3.exhausted is True
    # advisory still allows
    assert s3.allowed is True


def test_check_does_not_increment() -> None:
    """check is read-only relative to the call counter."""

    guard = ToolCallQuotaGuard(max_calls=5)
    guard.record("s", "csv")
    before = guard.check("s", "csv")
    again = guard.check("s", "csv")
    assert before.call_count == again.call_count == 1


def test_tools_and_sessions_are_isolated() -> None:
    """Different sessions and tools keep independent counters."""

    guard = ToolCallQuotaGuard(max_calls=1)
    guard.record("a", "search")
    assert guard.check("a", "search").exhausted is True
    assert guard.check("a", "fetch").call_count == 0
    assert guard.check("b", "search").call_count == 0


def test_hard_mode_raises_when_exhausted() -> None:
    """hard mode raises RuntimeError once the quota is exhausted."""

    guard = ToolCallQuotaGuard(max_calls=2, mode="hard")
    guard.record("sess", "tool")
    guard.record("sess", "tool")
    assert guard.check("sess", "tool").allowed is False
    with pytest.raises(RuntimeError, match="tool call quota exhausted"):
        guard.record("sess", "tool")
    assert guard.check("sess", "tool").call_count == 2


def test_advisory_mode_allows_recording_past_cap() -> None:
    """advisory mode still records past max_calls without raising."""

    guard = ToolCallQuotaGuard(max_calls=1, mode="advisory")
    guard.record("sess", "tool")
    over = guard.record("sess", "tool")
    assert over.call_count == 2
    assert over.exhausted is True
    assert over.allowed is True
    assert over.remaining == 0


def test_reset_clears_one_or_all_tools() -> None:
    """reset drops one tool or all tools for a session."""

    guard = ToolCallQuotaGuard(max_calls=1, mode="hard")
    guard.record("sess", "a")
    guard.record("sess", "b")
    assert guard.reset("sess", "a") is True
    assert guard.check("sess", "a").call_count == 0
    assert guard.check("sess", "b").call_count == 1
    assert guard.reset("sess") is True
    assert guard.check("sess", "b").call_count == 0
    assert guard.reset("sess") is False
    assert guard.record("sess", "a").call_count == 1


def test_constructor_rejects_bad_bounds() -> None:
    """Non-positive max_calls or invalid mode raises ValueError."""

    with pytest.raises(ValueError, match="max_calls"):
        ToolCallQuotaGuard(max_calls=0)
    with pytest.raises(ValueError, match="mode"):
        ToolCallQuotaGuard(max_calls=3, mode="soft")


def test_rejects_empty_ids() -> None:
    """Empty session_id or tool_name raises ValueError."""

    guard = ToolCallQuotaGuard(max_calls=2)
    with pytest.raises(ValueError, match="session_id"):
        guard.record("  ", "tool")
    with pytest.raises(ValueError, match="tool_name"):
        guard.record("s", "")
    with pytest.raises(ValueError, match="session_id"):
        guard.check("", "tool")
    with pytest.raises(ValueError, match="tool_name"):
        guard.reset("s", " ")
