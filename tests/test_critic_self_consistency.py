"""Unit tests for CriticSelfConsistencyBandGuard."""

from __future__ import annotations

import pytest

from multi_bot_agentic.critic_self_consistency import CriticSelfConsistencyBandGuard


def test_ok() -> None:
    """Low metric is ok."""

    status = CriticSelfConsistencyBandGuard().check("s1", disagreement_rate=0.125)
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_elevated() -> None:
    """Mid metric is elevated."""

    status = CriticSelfConsistencyBandGuard().check("s1", disagreement_rate=0.375)
    assert status.band == "elevated"


def test_blocked() -> None:
    """High metric is blocked."""

    status = CriticSelfConsistencyBandGuard().check("s1", disagreement_rate=0.75)
    assert status.band == "blocked"


def test_invalid() -> None:
    """Negative metric raises."""

    with pytest.raises(ValueError, match="disagreement_rate"):
        CriticSelfConsistencyBandGuard().check("s1", disagreement_rate=-1.0)
