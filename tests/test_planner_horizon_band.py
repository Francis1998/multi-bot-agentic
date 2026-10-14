"""Unit tests for PlannerHorizonBandAdvisor."""

from __future__ import annotations

import pytest

from multi_bot_agentic.planner_horizon_band import PlannerHorizonBandAdvisor


def test_ok() -> None:
    """Band ok."""

    status = PlannerHorizonBandAdvisor().advise("s1", horizon_steps_ratio=0.3000)
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_elevated() -> None:
    """Band elevated."""

    mid = (0.6 + 0.9) / 2
    status = PlannerHorizonBandAdvisor().advise("s1", horizon_steps_ratio=mid)
    assert status.band == "elevated"


def test_blocked() -> None:
    """Band blocked."""

    status = PlannerHorizonBandAdvisor().advise("s1", horizon_steps_ratio=1.8000)
    assert status.band == "blocked"


def test_invalid_raises() -> None:
    """Invalid metric raises ValueError."""

    with pytest.raises(ValueError, match="horizon_steps_ratio"):
        PlannerHorizonBandAdvisor().advise("s1", horizon_steps_ratio=-1.0)
