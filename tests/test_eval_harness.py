"""Tests for the offline evaluation harness metrics and runner."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.eval import (
    EvalScenario,
    EvaluationHarness,
    default_fixture_dir,
    load_scenarios,
    score_answer,
    score_tool_sequence,
)


def test_score_tool_sequence_prefix_match() -> None:
    """Tool-sequence score uses longest common prefix over expected length."""

    assert score_tool_sequence(("checklist", "echo"), ("checklist", "echo")) == 1.0
    assert score_tool_sequence(("checklist",), ("checklist", "echo")) == 0.5
    assert score_tool_sequence(("echo",), ("checklist",)) == 0.0
    assert score_tool_sequence((), ()) == 1.0
    assert score_tool_sequence(("echo",), ()) == 0.0


def test_score_answer_exact_and_contains() -> None:
    """Answer scoring supports exact match and substring checks."""

    assert score_answer("ok", expected_answer="ok") == 1.0
    assert score_answer("ok", expected_answer="nope") == 0.0
    assert score_answer("launch checklist ready", expected_answer_contains="checklist") == 1.0
    assert score_answer("launch", expected_answer_contains="checklist") == 0.0
    assert score_answer("anything") == 1.0


def test_harness_runs_packaged_fixtures(tmp_path: Path) -> None:
    """Packaged fixtures execute against Fake/scripted LLM and pass metrics."""

    scenarios = load_scenarios(default_fixture_dir())
    assert len(scenarios) >= 2
    report = EvaluationHarness(scenarios).run(root=tmp_path, event_log_dir=tmp_path / "logs")
    assert report.pass_rate == 1.0
    assert report.mean_tool_sequence_score == 1.0
    assert report.mean_answer_score == 1.0
    assert all(item.passed for item in report.scenarios)


def test_harness_detects_wrong_tool_sequence(tmp_path: Path) -> None:
    """A mismatched expected tool sequence fails the scenario."""

    scenario = EvalScenario(
        scenario_id="wrong_tool",
        goal="Create an agent launch checklist",
        scripted_responses=("TOOL:checklist:Create an agent launch checklist", "DONE: done"),
        expected_tools=("echo",),
        expected_answer="done",
        max_steps=5,
    )
    report = EvaluationHarness((scenario,)).run(root=tmp_path, event_log_dir=tmp_path / "logs")
    assert report.pass_rate == 0.0
    assert report.scenarios[0].tool_sequence_score == 0.0
    assert report.scenarios[0].actual_tools == ("checklist",)
