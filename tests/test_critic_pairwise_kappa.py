"""Unit tests for CriticPairwiseKappaGate."""

from __future__ import annotations

import pytest

from multi_bot_agentic.critic_pairwise_kappa import CriticPairwiseKappaGate


def test_ok() -> None:
    """High kappa is ok."""

    status = CriticPairwiseKappaGate().check("s1", kappa=0.85)
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_elevated() -> None:
    """Mid kappa is elevated."""

    status = CriticPairwiseKappaGate().check("s1", kappa=0.4)
    assert status.band == "elevated"


def test_blocked() -> None:
    """Low kappa is blocked."""

    status = CriticPairwiseKappaGate().check("s1", kappa=0.05)
    assert status.band == "blocked"


def test_invalid() -> None:
    """Out-of-range kappa raises."""

    with pytest.raises(ValueError, match="kappa"):
        CriticPairwiseKappaGate().check("s1", kappa=1.5)
