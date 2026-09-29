"""Unit tests for CriticTimeoutBandGuard."""

from __future__ import annotations

import pytest

from multi_bot_agentic.critic_timeout_band import CriticTimeoutBandGuard


def test_within_budget() -> None:
    """Low ratio is within_budget."""

    status = CriticTimeoutBandGuard().check("s1", waited_s=1.0, timeout_s=10.0)
    assert status.band == "within_budget"
    assert status.requires_human_review is True


def test_approaching() -> None:
    """Mid ratio is approaching."""

    status = CriticTimeoutBandGuard().check("s1", waited_s=8.0, timeout_s=10.0)
    assert status.band == "approaching"


def test_timed_out() -> None:
    """At-or-over timeout is timed_out."""

    status = CriticTimeoutBandGuard().check("s1", waited_s=10.0, timeout_s=10.0)
    assert status.band == "timed_out"


def test_empty_session_raises() -> None:
    """Empty session id raises ValueError."""

    with pytest.raises(ValueError, match="session_id"):
        CriticTimeoutBandGuard().check(" ", waited_s=1.0, timeout_s=5.0)
