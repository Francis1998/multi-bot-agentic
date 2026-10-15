"""Unit tests for CriticQuorumHysteresisAdvisor."""

from __future__ import annotations

import pytest

from multi_bot_agentic.critic_quorum_hysteresis import CriticQuorumHysteresisAdvisor


def test_ok() -> None:
    """Band ok."""

    status = CriticQuorumHysteresisAdvisor().advise("s1", hysteresis_score=0.3000)
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_elevated() -> None:
    """Band elevated."""

    mid = (0.6 + 0.9) / 2
    status = CriticQuorumHysteresisAdvisor().advise("s1", hysteresis_score=mid)
    assert status.band == "elevated"


def test_blocked() -> None:
    """Band blocked."""

    status = CriticQuorumHysteresisAdvisor().advise("s1", hysteresis_score=1.8000)
    assert status.band == "blocked"


def test_invalid_raises() -> None:
    """Invalid metric raises ValueError."""

    with pytest.raises(ValueError, match="hysteresis_score"):
        CriticQuorumHysteresisAdvisor().advise("s1", hysteresis_score=-1.0)
