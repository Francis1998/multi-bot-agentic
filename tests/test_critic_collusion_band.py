"""Unit tests for CriticCollusionBandAdvisor."""

from __future__ import annotations

import pytest

from multi_bot_agentic.critic_collusion_band import CriticCollusionBandAdvisor


def test_ok() -> None:
    """Band ok."""

    status = CriticCollusionBandAdvisor().check("s1", collusion_score=0.1)
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_elevated() -> None:
    """Band elevated."""

    status = CriticCollusionBandAdvisor().check("s1", collusion_score=0.4)
    assert status.band == "elevated"


def test_blocked() -> None:
    """Band blocked."""

    status = CriticCollusionBandAdvisor().check("s1", collusion_score=0.9)
    assert status.band == "blocked"


def test_invalid_raises() -> None:
    """Invalid metric raises ValueError."""

    with pytest.raises(ValueError, match="collusion_score"):
        CriticCollusionBandAdvisor().check("s1", collusion_score=-1.0)
