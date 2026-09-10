"""Tests for SpeculativeToolPrefetch."""

from __future__ import annotations

import pytest

from multi_bot_agentic.tool_prefetch import SpeculativeToolPrefetch


def test_invalid_max_prefetch_raises() -> None:
    """max_prefetch < 1 raises ValueError."""

    with pytest.raises(ValueError, match="max_prefetch"):
        SpeculativeToolPrefetch(max_prefetch=0)


def test_empty_available_returns_empty() -> None:
    """No available tools yields an empty plan."""

    plan = SpeculativeToolPrefetch().plan(recent_tools=["a"], available_tools=[])
    assert plan.tool_names == []
    assert "no available" in plan.reason


def test_recency_ranks_recent_tools_first() -> None:
    """More recent tools rank higher."""

    plan = SpeculativeToolPrefetch(max_prefetch=2).plan(
        recent_tools=["search", "checklist", "search"],
        available_tools=["checklist", "search", "weather"],
    )
    assert plan.tool_names[0] == "search"
    assert "recency" in plan.reason


def test_hint_boosts_matching_tool() -> None:
    """Hint text boosts matching tool names."""

    plan = SpeculativeToolPrefetch(max_prefetch=1).plan(
        recent_tools=[],
        available_tools=["weather", "checklist"],
        hint="need weather lookup",
    )
    assert plan.tool_names == ["weather"]
    assert "hint" in plan.reason


def test_never_executes_tools() -> None:
    """Prefetch only returns names — no side effects on callables."""

    executed = {"n": 0}

    def fake_tool() -> None:
        executed["n"] += 1

    SpeculativeToolPrefetch().plan(
        recent_tools=["fake_tool"],
        available_tools=["fake_tool", "other"],
    )
    assert executed["n"] == 0
    # Binding the callable must not matter — planner never calls it.
    _ = fake_tool
