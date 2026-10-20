"""Tests for PlannerCriticOscillationBandAdvisor."""

from __future__ import annotations

import pytest

from multi_bot_agentic.planner_critic_oscillation_band import PlannerCriticOscillationBandAdvisor


def test_ok_band() -> None:
    """Below soft is ok."""

    status = PlannerCriticOscillationBandAdvisor().advise("s1", oscillation_ratio=0.1)
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_elevated_band() -> None:
    """Between soft and hard is elevated."""

    status = PlannerCriticOscillationBandAdvisor(soft_limit=0.2, hard_limit=0.55).advise("s1", oscillation_ratio=0.375)
    assert status.band == "elevated"


def test_blocked_band() -> None:
    """Above hard is blocked."""

    status = PlannerCriticOscillationBandAdvisor(soft_limit=0.2, hard_limit=0.55).advise("s1", oscillation_ratio=0.75)
    assert status.band == "blocked"


def test_invalid_session() -> None:
    """Empty session_id raises."""

    with pytest.raises(ValueError, match="session_id"):
        PlannerCriticOscillationBandAdvisor().advise("  ", oscillation_ratio=0.1)


def test_invalid_metric() -> None:
    """Negative metric raises."""

    with pytest.raises(ValueError, match="oscillation_ratio"):
        PlannerCriticOscillationBandAdvisor().advise("s1", oscillation_ratio=-0.1)


def test_invalid_limits() -> None:
    """Bad ctor limits raise."""

    with pytest.raises(ValueError, match="hard_limit"):
        PlannerCriticOscillationBandAdvisor(soft_limit=0.5, hard_limit=0.2)
