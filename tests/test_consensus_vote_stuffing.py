"""Unit tests for ConsensusVoteStuffingBandAdvisor."""

from __future__ import annotations

import pytest

from multi_bot_agentic.consensus_vote_stuffing import ConsensusVoteStuffingBandAdvisor


def test_ok() -> None:
    """Band ok."""

    status = ConsensusVoteStuffingBandAdvisor().advise("s1", stuffing_score=0.1)
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_elevated() -> None:
    """Band elevated."""

    status = ConsensusVoteStuffingBandAdvisor().advise("s1", stuffing_score=0.4)
    assert status.band == "elevated"


def test_blocked() -> None:
    """Band blocked."""

    status = ConsensusVoteStuffingBandAdvisor().advise("s1", stuffing_score=0.9)
    assert status.band == "blocked"


def test_invalid_raises() -> None:
    """Invalid metric raises ValueError."""

    with pytest.raises(ValueError, match="stuffing_score"):
        ConsensusVoteStuffingBandAdvisor().advise("s1", stuffing_score=-1.0)
