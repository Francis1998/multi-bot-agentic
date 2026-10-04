"""Unit tests for CriticTokenBudgetBandGuard."""

from __future__ import annotations

import pytest

from multi_bot_agentic.critic_token_budget import CriticTokenBudgetBandGuard


def test_ok() -> None:
    """Low metric is ok."""

    status = CriticTokenBudgetBandGuard().check("s1", tokens_used=1000.0)
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_elevated() -> None:
    """Mid metric is elevated."""

    status = CriticTokenBudgetBandGuard().check("s1", tokens_used=5000.0)
    assert status.band == "elevated"


def test_blocked() -> None:
    """High metric is blocked."""

    status = CriticTokenBudgetBandGuard().check("s1", tokens_used=9000.0)
    assert status.band == "blocked"


def test_invalid() -> None:
    """Negative metric raises."""

    with pytest.raises(ValueError, match="tokens_used"):
        CriticTokenBudgetBandGuard().check("s1", tokens_used=-1.0)
