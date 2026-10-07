"""Unit tests for ConsensusQuorumBandGuard."""

from __future__ import annotations

import pytest

from multi_bot_agentic.consensus_quorum_band import ConsensusQuorumBandGuard


def test_ok() -> None:
    """Low shortfall is ok."""

    status = ConsensusQuorumBandGuard().check("s1", shortfall_ratio=0.1)
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_elevated() -> None:
    """Mid shortfall is elevated."""

    status = ConsensusQuorumBandGuard().check("s1", shortfall_ratio=0.35)
    assert status.band == "elevated"


def test_blocked() -> None:
    """High shortfall is blocked."""

    status = ConsensusQuorumBandGuard().check("s1", shortfall_ratio=0.8)
    assert status.band == "blocked"


def test_invalid() -> None:
    """Negative metric raises."""

    with pytest.raises(ValueError, match="shortfall_ratio"):
        ConsensusQuorumBandGuard().check("s1", shortfall_ratio=-1.0)
