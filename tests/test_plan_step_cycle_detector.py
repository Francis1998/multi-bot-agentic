"""Unit tests for PlanStepCycleDetectorGuard."""

from __future__ import annotations

import pytest

from multi_bot_agentic.plan_step_cycle_detector import PlanStepCycleDetectorGuard


def test_ok() -> None:
    """Band ok."""

    status = PlanStepCycleDetectorGuard().check("s1", cycle_score=0.1)
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_elevated() -> None:
    """Band elevated."""

    status = PlanStepCycleDetectorGuard().check("s1", cycle_score=0.4)
    assert status.band == "elevated"


def test_blocked() -> None:
    """Band blocked."""

    status = PlanStepCycleDetectorGuard().check("s1", cycle_score=0.9)
    assert status.band == "blocked"


def test_invalid_raises() -> None:
    """Invalid metric raises ValueError."""

    with pytest.raises(ValueError, match="cycle_score"):
        PlanStepCycleDetectorGuard().check("s1", cycle_score=-1.0)
