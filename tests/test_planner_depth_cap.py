"""Unit tests for PlannerDepthCapAdvisor."""

from __future__ import annotations

import pytest

from multi_bot_agentic.planner_depth_cap import PlannerDepthCapAdvisor


def test_ok() -> None:
    """Low metric is ok."""

    status = PlannerDepthCapAdvisor().advise("s1", plan_depth=2.0)
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_elevated() -> None:
    """Mid metric is elevated."""

    status = PlannerDepthCapAdvisor().advise("s1", plan_depth=10.0)
    assert status.band == "elevated"


def test_blocked() -> None:
    """High metric is blocked."""

    status = PlannerDepthCapAdvisor().advise("s1", plan_depth=20.0)
    assert status.band == "blocked"


def test_invalid() -> None:
    """Negative metric raises."""

    with pytest.raises(ValueError, match="plan_depth"):
        PlannerDepthCapAdvisor().advise("s1", plan_depth=-1.0)
