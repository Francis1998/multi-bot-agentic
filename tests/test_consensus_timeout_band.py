"""Unit tests for ConsensusTimeoutBandGuard."""

from __future__ import annotations

import pytest

from multi_bot_agentic.consensus_timeout_band import ConsensusTimeoutBandGuard


def test_within_budget() -> None:
    """Under 70% of timeout is within_budget."""

    status = ConsensusTimeoutBandGuard().check("s1", waited_s=2.0, timeout_s=10.0)
    assert status.band == "within_budget"
    assert status.requires_human_review is True


def test_approaching() -> None:
    """70%+ of timeout is approaching."""

    status = ConsensusTimeoutBandGuard().check("s1", waited_s=8.0, timeout_s=10.0)
    assert status.band == "approaching"


def test_timed_out() -> None:
    """At/over timeout is timed_out."""

    status = ConsensusTimeoutBandGuard().check("s1", waited_s=10.0, timeout_s=10.0)
    assert status.band == "timed_out"


def test_empty_session_raises() -> None:
    """Empty session id raises ValueError."""

    with pytest.raises(ValueError, match="session_id"):
        ConsensusTimeoutBandGuard().check(" ", waited_s=0.0, timeout_s=1.0)
