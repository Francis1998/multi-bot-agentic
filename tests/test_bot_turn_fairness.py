"""Tests for BotTurnFairnessScheduler."""

from __future__ import annotations

import pytest

from multi_bot_agentic.bot_turn_fairness import BotTurnFairnessScheduler


def test_recommends_least_served() -> None:
    """Recommend the bot with the fewest recorded turns."""

    sched = BotTurnFairnessScheduler(max_skew=2, mode="advisory")
    sched.record("s1", "alpha", ["alpha", "beta"])
    snap = sched.recommend("s1", ["alpha", "beta"])
    assert snap.recommended_bot_id == "beta"
    assert snap.counts["alpha"] == 1
    assert snap.counts["beta"] == 0


def test_hard_mode_blocks_skew() -> None:
    """Hard mode raises when recording would exceed max_skew."""

    sched = BotTurnFairnessScheduler(max_skew=0, mode="hard")
    sched.record("s1", "alpha", ["alpha", "beta"])
    with pytest.raises(RuntimeError, match="skew"):
        sched.record("s1", "alpha", ["alpha", "beta"])


def test_reset_clears_session() -> None:
    """reset removes session counts."""

    sched = BotTurnFairnessScheduler()
    sched.record("s1", "alpha", ["alpha"])
    assert sched.reset("s1") is True
    assert sched.reset("s1") is False


def test_empty_session_raises() -> None:
    """Empty session_id raises ValueError."""

    with pytest.raises(ValueError, match="session_id"):
        BotTurnFairnessScheduler().recommend("  ", ["a"])
