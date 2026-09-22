"""Unit tests for ToolCallWaveScheduler."""

from __future__ import annotations

from pathlib import Path

import pytest

from multi_bot_agentic.tool_call_wave import ToolCallWaveScheduler


def test_independent_tools_one_wave() -> None:
    """Tools without deps share a single wave."""

    plan = ToolCallWaveScheduler().plan({"a": [], "b": []})
    assert plan.waves == (("a", "b"),)
    assert plan.wave_count == 1


def test_dependency_creates_two_waves() -> None:
    """Dependent tool waits for the next wave."""

    plan = ToolCallWaveScheduler().plan({"a": [], "b": ["a"]})
    assert plan.waves == (("a",), ("b",))


def test_hard_cycle_raises() -> None:
    """Hard mode raises on cyclic dependencies."""

    with pytest.raises(ValueError, match="cyclic"):
        ToolCallWaveScheduler(mode="hard").plan({"a": ["b"], "b": ["a"]})


def test_advisory_cycle_dumps_final_wave() -> None:
    """Advisory mode emits unresolved cyclic tools as a final wave."""

    plan = ToolCallWaveScheduler(mode="advisory").plan({"a": ["b"], "b": ["a"]})
    assert plan.waves == (("a", "b"),)


def test_unknown_dep_hard_raises() -> None:
    """Hard mode raises on unknown dependency ids."""

    with pytest.raises(ValueError, match="unknown"):
        ToolCallWaveScheduler(mode="hard").plan({"a": ["missing"]})


def test_module_has_no_httpx_import() -> None:
    """Feature module must not import httpx (CI has no httpx)."""

    source = Path(__file__).resolve().parents[1] / "src/multi_bot_agentic/tool_call_wave.py"
    assert "httpx" not in source.read_text(encoding="utf-8")
