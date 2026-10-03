"""Unit tests for PlannerCostCeilingAdvisor."""

from __future__ import annotations

import pytest

from multi_bot_agentic.planner_cost_ceiling import PlannerCostCeilingAdvisor


def test_ok() -> None:
    """Low metric is ok."""

    status = PlannerCostCeilingAdvisor().advise("s1", cost_usd=0.5)
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_elevated() -> None:
    """Mid metric is elevated."""

    status = PlannerCostCeilingAdvisor().advise("s1", cost_usd=3.0)
    assert status.band == "elevated"


def test_blocked() -> None:
    """High metric is blocked."""

    status = PlannerCostCeilingAdvisor().advise("s1", cost_usd=5.1)
    assert status.band == "blocked"


def test_invalid() -> None:
    """Negative metric raises."""

    with pytest.raises(ValueError, match="cost_usd"):
        PlannerCostCeilingAdvisor().advise("s1", cost_usd=-1.0)
