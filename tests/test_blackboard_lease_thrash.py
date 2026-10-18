"""Tests for BlackboardLeaseThrashAdvisor."""

from __future__ import annotations

import pytest

from multi_bot_agentic.blackboard_lease_thrash import BlackboardLeaseThrashAdvisor


def test_ok_band() -> None:
    """Below soft is ok."""

    status = BlackboardLeaseThrashAdvisor().advise("s1", thrash_ratio=0.1)
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_elevated_band() -> None:
    """Between soft and hard is elevated."""

    status = BlackboardLeaseThrashAdvisor(soft_limit=0.2, hard_limit=0.5).advise("s1", thrash_ratio=0.3)
    assert status.band == "elevated"


def test_blocked_band() -> None:
    """Above hard is blocked."""

    status = BlackboardLeaseThrashAdvisor(soft_limit=0.2, hard_limit=0.5).advise("s1", thrash_ratio=0.9)
    assert status.band == "blocked"


def test_invalid_session() -> None:
    """Empty session_id raises."""

    with pytest.raises(ValueError, match="session_id"):
        BlackboardLeaseThrashAdvisor().advise("  ", thrash_ratio=0.1)


def test_invalid_metric() -> None:
    """Negative metric raises."""

    with pytest.raises(ValueError, match="thrash_ratio"):
        BlackboardLeaseThrashAdvisor().advise("s1", thrash_ratio=-0.1)


def test_invalid_limits() -> None:
    """Bad ctor limits raise."""

    with pytest.raises(ValueError, match="hard_limit"):
        BlackboardLeaseThrashAdvisor(soft_limit=0.5, hard_limit=0.2)
