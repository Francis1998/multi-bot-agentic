"""Tests for PlanStepDependencyResolver."""

from __future__ import annotations

import pytest

from multi_bot_agentic.plan_step_dependency import PlanStep, PlanStepDependencyResolver


def test_linear_order() -> None:
    """A→B→C resolves in declaration-stable order."""

    steps = [
        PlanStep("a"),
        PlanStep("b", depends_on=("a",)),
        PlanStep("c", depends_on=("b",)),
    ]
    result = PlanStepDependencyResolver().resolve(steps)
    assert result.ok is True
    assert result.order == ("a", "b", "c")
    assert result.cyclic is False


def test_cycle_detected() -> None:
    """Mutual dependencies yield cyclic=True."""

    steps = [
        PlanStep("a", depends_on=("b",)),
        PlanStep("b", depends_on=("a",)),
    ]
    result = PlanStepDependencyResolver().resolve(steps)
    assert result.ok is False
    assert result.cyclic is True


def test_missing_dep() -> None:
    """Unknown dependency ids are reported."""

    steps = [PlanStep("a", depends_on=("missing",))]
    result = PlanStepDependencyResolver().resolve(steps)
    assert result.ok is False
    assert result.missing_deps == ("missing",)


def test_empty_ok() -> None:
    """Empty plan is ok with empty order."""

    result = PlanStepDependencyResolver().resolve([])
    assert result.ok is True
    assert result.order == ()


def test_duplicate_raises() -> None:
    """Duplicate step ids raise ValueError."""

    with pytest.raises(ValueError, match="duplicate"):
        PlanStepDependencyResolver().resolve([PlanStep("a"), PlanStep("a")])
