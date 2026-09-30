"""Unit tests for CriticAgreementEntropyGate."""

from __future__ import annotations

import pytest

from multi_bot_agentic.critic_agreement_entropy import CriticAgreementEntropyGate


def test_ok_band_unanimous() -> None:
    """Unanimous verdicts have zero entropy."""

    status = CriticAgreementEntropyGate(soft_limit=0.5, hard_limit=1.0).check(
        "s1", verdicts=["approve", "approve", "approve"]
    )
    assert status.band == "ok"
    assert status.entropy == 0.0
    assert status.requires_human_review is True


def test_soft_band() -> None:
    """Moderate disagreement hits soft."""

    status = CriticAgreementEntropyGate(soft_limit=0.5, hard_limit=1.2).check("s1", verdicts=["a", "a", "b", "c"])
    assert status.band == "soft"
    assert status.unique_labels == 3


def test_hard_band_max_entropy() -> None:
    """High entropy hits hard."""

    status = CriticAgreementEntropyGate(soft_limit=0.3, hard_limit=0.9).check("s1", verdicts=["a", "b", "c", "d"])
    assert status.band == "hard"


def test_empty_verdicts() -> None:
    """Empty verdicts raise."""

    with pytest.raises(ValueError, match="verdicts"):
        CriticAgreementEntropyGate().check("s1", verdicts=[])


def test_blank_label() -> None:
    """Blank label raises."""

    with pytest.raises(ValueError, match="non-empty"):
        CriticAgreementEntropyGate().check("s1", verdicts=["ok", "  "])


def test_invalid_limits() -> None:
    """Bad ctor limits raise."""

    with pytest.raises(ValueError, match="soft_limit"):
        CriticAgreementEntropyGate(soft_limit=0.0, hard_limit=1.0)


def test_empty_session() -> None:
    """Empty session raises."""

    with pytest.raises(ValueError, match="session_id"):
        CriticAgreementEntropyGate().check("", verdicts=["a"])
