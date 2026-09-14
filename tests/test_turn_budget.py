"""Tests for ConversationTurnBudgetGuard."""

from __future__ import annotations

import pytest

from multi_bot_agentic.turn_budget import ConversationTurnBudgetGuard


def test_record_turn_increments_until_exhausted() -> None:
    """Turns increment and exhausted flips at max_turns."""

    guard = ConversationTurnBudgetGuard(max_turns=3, mode="advisory")
    s1 = guard.record_turn("sess-1")
    assert s1.turn_count == 1
    assert s1.remaining == 2
    assert s1.exhausted is False
    guard.record_turn("sess-1")
    s3 = guard.record_turn("sess-1")
    assert s3.turn_count == 3
    assert s3.remaining == 0
    assert s3.exhausted is True


def test_check_does_not_increment() -> None:
    """check is read-only relative to the turn counter."""

    guard = ConversationTurnBudgetGuard(max_turns=5)
    guard.record_turn("s")
    before = guard.check("s")
    again = guard.check("s")
    assert before.turn_count == again.turn_count == 1


def test_sessions_are_isolated() -> None:
    """Different sessions keep independent counters."""

    guard = ConversationTurnBudgetGuard(max_turns=2)
    guard.record_turn("a")
    guard.record_turn("a")
    assert guard.check("a").exhausted is True
    assert guard.check("b").turn_count == 0
    assert guard.check("b").exhausted is False


def test_hard_mode_raises_when_exhausted() -> None:
    """hard mode raises RuntimeError once the budget is exhausted."""

    guard = ConversationTurnBudgetGuard(max_turns=2, mode="hard")
    guard.record_turn("sess")
    guard.record_turn("sess")
    with pytest.raises(RuntimeError, match="turn budget exhausted"):
        guard.record_turn("sess")
    assert guard.check("sess").turn_count == 2


def test_advisory_mode_allows_recording_past_cap() -> None:
    """advisory mode still records past max_turns without raising."""

    guard = ConversationTurnBudgetGuard(max_turns=1, mode="advisory")
    guard.record_turn("sess")
    over = guard.record_turn("sess")
    assert over.turn_count == 2
    assert over.exhausted is True
    assert over.remaining == 0


def test_reset_clears_counter() -> None:
    """reset drops the counter so the session can continue."""

    guard = ConversationTurnBudgetGuard(max_turns=1, mode="hard")
    guard.record_turn("sess")
    assert guard.reset("sess") is True
    assert guard.check("sess").turn_count == 0
    assert guard.reset("sess") is False
    # After reset, hard mode accepts another turn.
    assert guard.record_turn("sess").turn_count == 1


def test_constructor_rejects_bad_bounds() -> None:
    """Non-positive max_turns or invalid mode raises ValueError."""

    with pytest.raises(ValueError, match="max_turns"):
        ConversationTurnBudgetGuard(max_turns=0)
    with pytest.raises(ValueError, match="mode"):
        ConversationTurnBudgetGuard(max_turns=3, mode="soft")


def test_rejects_empty_session_id() -> None:
    """Empty session_id raises ValueError."""

    guard = ConversationTurnBudgetGuard(max_turns=2)
    with pytest.raises(ValueError, match="session_id"):
        guard.record_turn("  ")
    with pytest.raises(ValueError, match="session_id"):
        guard.check("")
    with pytest.raises(ValueError, match="session_id"):
        guard.reset(" ")
