"""Unit tests for MultiBotLatencyBudgetAllocator."""

from __future__ import annotations

import pytest

from multi_bot_agentic.multi_bot_latency_budget import (
    MultiBotLatencyBudgetAllocator,
)


def test_within() -> None:
    """Low utilization is within."""

    status = MultiBotLatencyBudgetAllocator().check("s1", bot_id="planner", allocated_ms=1000.0, used_ms=500.0)
    assert status.band == "within"
    assert status.requires_human_review is True


def test_soft() -> None:
    """Near allocation is soft."""

    status = MultiBotLatencyBudgetAllocator().check("s1", bot_id="planner", allocated_ms=1000.0, used_ms=900.0)
    assert status.band == "soft"


def test_breach() -> None:
    """Over allocation is breach."""

    status = MultiBotLatencyBudgetAllocator().check("s1", bot_id="planner", allocated_ms=1000.0, used_ms=1200.0)
    assert status.band == "breach"


def test_invalid_allocated() -> None:
    """Non-positive allocated raises."""

    with pytest.raises(ValueError, match="allocated_ms"):
        MultiBotLatencyBudgetAllocator().check("s1", bot_id="x", allocated_ms=0.0, used_ms=0.0)


def test_over_budget_alloc() -> None:
    """Allocation above session budget raises."""

    with pytest.raises(ValueError, match="session_budget"):
        MultiBotLatencyBudgetAllocator(session_budget_ms=100.0).check("s1", bot_id="x", allocated_ms=200.0, used_ms=0.0)


def test_empty_bot() -> None:
    """Empty bot raises."""

    with pytest.raises(ValueError, match="bot_id"):
        MultiBotLatencyBudgetAllocator().check("s1", bot_id=" ", allocated_ms=10.0, used_ms=0.0)
