"""Unit tests for CriticTimeoutCascadeGuard."""

from __future__ import annotations

import pytest

from multi_bot_agentic.critic_timeout_cascade import CriticTimeoutCascadeGuard


def test_ok() -> None:
    """Band ok."""

    status = CriticTimeoutCascadeGuard().check("s1", cascade_score=0.1)
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_elevated() -> None:
    """Band elevated."""

    status = CriticTimeoutCascadeGuard().check("s1", cascade_score=0.4)
    assert status.band == "elevated"


def test_blocked() -> None:
    """Band blocked."""

    status = CriticTimeoutCascadeGuard().check("s1", cascade_score=0.9)
    assert status.band == "blocked"


def test_invalid_raises() -> None:
    """Invalid metric raises ValueError."""

    with pytest.raises(ValueError, match="cascade_score"):
        CriticTimeoutCascadeGuard().check("s1", cascade_score=-1.0)
