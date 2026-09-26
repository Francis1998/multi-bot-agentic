"""Unit tests for ConsensusQuorumFloorGuard."""

from __future__ import annotations

import pytest

from multi_bot_agentic.consensus_quorum_floor import ConsensusQuorumFloorGuard


def test_quorum_met() -> None:
    """Yes votes at floor is quorum_met."""

    status = ConsensusQuorumFloorGuard().check("s1", yes_votes=3, min_yes_votes=3)
    assert status.band == "quorum_met"
    assert status.shortfall == 0
    assert status.requires_human_review is True


def test_near_quorum() -> None:
    """Partial yes votes is near_quorum."""

    status = ConsensusQuorumFloorGuard().check("s1", yes_votes=2, min_yes_votes=3)
    assert status.band == "near_quorum"
    assert status.shortfall == 1


def test_quorum_fail() -> None:
    """Thin yes votes is quorum_fail."""

    status = ConsensusQuorumFloorGuard().check("s1", yes_votes=0, min_yes_votes=3)
    assert status.band == "quorum_fail"


def test_empty_session_raises() -> None:
    """Empty session id raises ValueError."""

    with pytest.raises(ValueError, match="session_id"):
        ConsensusQuorumFloorGuard().check("", yes_votes=1)
