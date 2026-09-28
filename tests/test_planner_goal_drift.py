"""Unit tests for PlannerGoalDriftGuard."""

from __future__ import annotations

import pytest

from multi_bot_agentic.planner_goal_drift import PlannerGoalDriftGuard


def test_aligned_band() -> None:
    """High token overlap is aligned."""

    status = PlannerGoalDriftGuard().check(
        "s1",
        plan_goal="summarize research papers about transformers",
        step_goal="summarize research papers about transformers carefully",
    )
    assert status.band == "aligned"
    assert status.requires_human_review is True


def test_drifting_band() -> None:
    """Partial overlap is drifting."""

    status = PlannerGoalDriftGuard().check(
        "s1",
        plan_goal="summarize research papers",
        step_goal="summarize budget spreadsheet",
    )
    assert status.band == "drifting"


def test_diverged_band() -> None:
    """Low overlap is diverged."""

    status = PlannerGoalDriftGuard().check(
        "s1",
        plan_goal="summarize research papers",
        step_goal="book flight tickets tomorrow",
    )
    assert status.band == "diverged"


def test_empty_session_raises() -> None:
    """Empty session id raises ValueError."""

    with pytest.raises(ValueError, match="session_id"):
        PlannerGoalDriftGuard().check(" ", plan_goal="a b", step_goal="a b")
