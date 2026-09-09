"""Tests for BudgetedStepPlanner."""

from __future__ import annotations

import pytest

from multi_bot_agentic.budget_planner import BudgetedStepPlanner


def test_clamps_by_tokens() -> None:
    """Allowed steps shrink when the token budget is the tighter constraint."""

    planner = BudgetedStepPlanner()
    plan = planner.plan(max_steps=10, max_tokens=3000, estimated_tokens_per_step=1000)
    assert plan.allowed_steps == 3
    assert "token" in plan.reason
    assert planner.remaining_tokens == 3000
    assert planner.remaining_steps == 3


def test_limited_by_max_steps() -> None:
    """When tokens allow more steps, max_steps wins."""

    planner = BudgetedStepPlanner()
    plan = planner.plan(max_steps=2, max_tokens=50_000, estimated_tokens_per_step=100)
    assert plan.allowed_steps == 2
    assert "max_steps" in plan.reason


def test_rejects_non_positive_knobs() -> None:
    """Non-positive planning knobs raise ValueError."""

    planner = BudgetedStepPlanner()
    with pytest.raises(ValueError):
        planner.plan(max_steps=0, max_tokens=100, estimated_tokens_per_step=10)
    with pytest.raises(ValueError):
        planner.plan(max_steps=5, max_tokens=0, estimated_tokens_per_step=10)
    with pytest.raises(ValueError):
        planner.plan(max_steps=5, max_tokens=100, estimated_tokens_per_step=0)


def test_reserve_tracks_remaining() -> None:
    """reserve decrements remaining tokens and steps."""

    planner = BudgetedStepPlanner()
    planner.plan(max_steps=3, max_tokens=900, estimated_tokens_per_step=300)
    planner.reserve(250)
    assert planner.remaining_tokens == 650
    assert planner.remaining_steps == 2


def test_token_budget_too_small() -> None:
    """When one step cannot fit, allowed_steps is zero."""

    planner = BudgetedStepPlanner()
    plan = planner.plan(max_steps=5, max_tokens=50, estimated_tokens_per_step=100)
    assert plan.allowed_steps == 0
    assert planner.remaining_steps == 0
