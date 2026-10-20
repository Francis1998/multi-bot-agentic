"""Tests for ActorMailboxOverflowAdvisor."""

from __future__ import annotations

import pytest

from multi_bot_agentic.actor_mailbox_overflow import ActorMailboxOverflowAdvisor


def test_ok_band() -> None:
    """Below soft is ok."""

    status = ActorMailboxOverflowAdvisor().advise("s1", mailbox_depth_ratio=0.1)
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_elevated_band() -> None:
    """Between soft and hard is elevated."""

    status = ActorMailboxOverflowAdvisor(soft_limit=0.25, hard_limit=0.6).advise("s1", mailbox_depth_ratio=0.425)
    assert status.band == "elevated"


def test_blocked_band() -> None:
    """Above hard is blocked."""

    status = ActorMailboxOverflowAdvisor(soft_limit=0.25, hard_limit=0.6).advise("s1", mailbox_depth_ratio=0.8)
    assert status.band == "blocked"


def test_invalid_session() -> None:
    """Empty session_id raises."""

    with pytest.raises(ValueError, match="session_id"):
        ActorMailboxOverflowAdvisor().advise("  ", mailbox_depth_ratio=0.1)


def test_invalid_metric() -> None:
    """Negative metric raises."""

    with pytest.raises(ValueError, match="mailbox_depth_ratio"):
        ActorMailboxOverflowAdvisor().advise("s1", mailbox_depth_ratio=-0.1)


def test_invalid_limits() -> None:
    """Bad ctor limits raise."""

    with pytest.raises(ValueError, match="hard_limit"):
        ActorMailboxOverflowAdvisor(soft_limit=0.5, hard_limit=0.2)
