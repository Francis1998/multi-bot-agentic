"""Unit tests for PlannerReplanBudgetLimiter."""

from __future__ import annotations

import pytest

from multi_bot_agentic.planner_replan_budget import PlannerReplanBudgetLimiter


def test_ok_band() -> None:
    """Low replan count is ok."""

    status = PlannerReplanBudgetLimiter().check("s1", replan_count=0, max_replans=3)
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_warning_band() -> None:
    """Near-limit replan count is warning."""

    status = PlannerReplanBudgetLimiter().check("s1", replan_count=2, max_replans=3)
    assert status.band == "warning"


def test_exhausted_band() -> None:
    """At max replans is exhausted."""

    status = PlannerReplanBudgetLimiter().check("s1", replan_count=3, max_replans=3)
    assert status.band == "exhausted"


def test_empty_session_raises() -> None:
    """Empty session id raises ValueError."""

    with pytest.raises(ValueError, match="session_id"):
        PlannerReplanBudgetLimiter().check(" ", replan_count=0)
