"""Tests for SessionTokenBudgetLedger."""

from __future__ import annotations

import pytest

from multi_bot_agentic.session_token_budget import SessionTokenBudgetLedger


def test_record_accumulates_and_reports_ok() -> None:
    """Recording under soft_limit yields status ok."""

    ledger = SessionTokenBudgetLedger(soft_limit=100, hard_limit=200)
    status = ledger.record("sess-1", prompt_tokens=40, completion_tokens=10)
    assert status.prompt_tokens == 40
    assert status.completion_tokens == 10
    assert status.total_tokens == 50
    assert status.status == "ok"
    assert status.remaining_to_hard == 150


def test_soft_threshold_status() -> None:
    """Crossing soft_limit (but not hard) yields soft status."""

    ledger = SessionTokenBudgetLedger(soft_limit=50, hard_limit=100)
    ledger.record("s", prompt_tokens=30, completion_tokens=10)
    soft = ledger.record("s", prompt_tokens=10, completion_tokens=0)
    assert soft.total_tokens == 50
    assert soft.status == "soft"
    assert soft.remaining_to_hard == 50


def test_hard_threshold_status_never_raises() -> None:
    """Crossing hard_limit yields hard status without raising."""

    ledger = SessionTokenBudgetLedger(soft_limit=10, hard_limit=20)
    ledger.record("s", prompt_tokens=15, completion_tokens=0)
    hard = ledger.record("s", prompt_tokens=10, completion_tokens=0)
    assert hard.total_tokens == 25
    assert hard.status == "hard"
    assert hard.remaining_to_hard == 0
    # Still records past hard — never kills processes.
    past = ledger.record("s", prompt_tokens=5, completion_tokens=5)
    assert past.total_tokens == 35
    assert past.status == "hard"


def test_check_does_not_mutate() -> None:
    """check is read-only relative to counters."""

    ledger = SessionTokenBudgetLedger(soft_limit=100, hard_limit=200)
    ledger.record("s", prompt_tokens=20, completion_tokens=5)
    before = ledger.check("s")
    again = ledger.check("s")
    assert before.total_tokens == again.total_tokens == 25
    assert before.status == again.status == "ok"


def test_sessions_are_isolated() -> None:
    """Different sessions keep independent ledgers."""

    ledger = SessionTokenBudgetLedger(soft_limit=10, hard_limit=20)
    ledger.record("a", prompt_tokens=20, completion_tokens=0)
    assert ledger.check("a").status == "hard"
    assert ledger.check("b").total_tokens == 0
    assert ledger.check("b").status == "ok"


def test_reset_clears_counters() -> None:
    """reset drops counters so the session can continue under budget."""

    ledger = SessionTokenBudgetLedger(soft_limit=10, hard_limit=20)
    ledger.record("sess", prompt_tokens=25, completion_tokens=0)
    assert ledger.reset("sess") is True
    assert ledger.check("sess").total_tokens == 0
    assert ledger.check("sess").status == "ok"
    assert ledger.reset("sess") is False


def test_constructor_rejects_bad_bounds() -> None:
    """Non-positive limits or soft > hard raises ValueError."""

    with pytest.raises(ValueError, match="soft_limit"):
        SessionTokenBudgetLedger(soft_limit=0, hard_limit=10)
    with pytest.raises(ValueError, match="hard_limit"):
        SessionTokenBudgetLedger(soft_limit=10, hard_limit=0)
    with pytest.raises(ValueError, match="soft_limit must be <="):
        SessionTokenBudgetLedger(soft_limit=50, hard_limit=10)


def test_rejects_empty_session_and_negative_tokens() -> None:
    """Empty session_id or negative token counts raise ValueError."""

    ledger = SessionTokenBudgetLedger(soft_limit=10, hard_limit=20)
    with pytest.raises(ValueError, match="session_id"):
        ledger.record("  ", prompt_tokens=1, completion_tokens=0)
    with pytest.raises(ValueError, match="session_id"):
        ledger.check("")
    with pytest.raises(ValueError, match="session_id"):
        ledger.reset(" ")
    with pytest.raises(ValueError, match="prompt_tokens"):
        ledger.record("s", prompt_tokens=-1, completion_tokens=0)
    with pytest.raises(ValueError, match="completion_tokens"):
        ledger.record("s", prompt_tokens=0, completion_tokens=-1)
