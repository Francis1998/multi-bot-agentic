"""Unit tests for PlannerStepBudgetBandAdvisor."""

from __future__ import annotations

import pytest

from multi_bot_agentic.planner_step_budget_band import PlannerStepBudgetBandAdvisor


def test_ok() -> None:
    """Band ok."""

    status = PlannerStepBudgetBandAdvisor().advise("s1", steps_used_ratio=0.3000)
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_elevated() -> None:
    """Band elevated."""

    mid = (0.6 + 0.9) / 2
    status = PlannerStepBudgetBandAdvisor().advise("s1", steps_used_ratio=mid)
    assert status.band == "elevated"


def test_blocked() -> None:
    """Band blocked."""

    status = PlannerStepBudgetBandAdvisor().advise("s1", steps_used_ratio=1.8000)
    assert status.band == "blocked"


def test_invalid_raises() -> None:
    """Invalid metric raises ValueError."""

    with pytest.raises(ValueError, match="steps_used_ratio"):
        PlannerStepBudgetBandAdvisor().advise("s1", steps_used_ratio=-1.0)
