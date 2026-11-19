"""Tests for the offline evaluation harness metrics and runner."""

from __future__ import annotations

from pathlib import Path

import pytest

from multi_bot_agentic.eval import (
    EvalScenario,
    EvaluationHarness,
    ScenarioScore,
    default_fixture_dir,
    load_scenarios,
    score_answer,
    score_tool_sequence,
)
from multi_bot_agentic.event_log import SQLiteEventLog


def test_score_tool_sequence_prefix_match() -> None:
    """Tool-sequence score uses longest common prefix over expected length."""

    assert score_tool_sequence(("checklist", "echo"), ("checklist", "echo")) == 1.0
    assert score_tool_sequence(("checklist",), ("checklist", "echo")) == 0.5
    assert score_tool_sequence(("echo",), ("checklist",)) == 0.0
    assert score_tool_sequence((), ()) == 1.0
    assert score_tool_sequence(("echo",), ()) == 0.0


@pytest.mark.parametrize("actual", [("echo", "rot13"), ("echo", "echo")], ids=["unexpected-tool", "repeated-tool"])
def test_score_tool_sequence_counts_calls_beyond_the_expected_tools(actual: tuple[str, ...]) -> None:
    """A call after the expected tools lowers the score, just as any call does when none is expected."""

    assert score_tool_sequence(actual, ("echo",)) == 0.5


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


def test_harness_fails_a_run_that_calls_a_tool_after_the_expected_ones(tmp_path: Path) -> None:
    """``expected_tools`` is the whole sequence, so a run that goes on to call another tool fails.

    A scenario expecting no tools already failed on any call, but one expecting ``echo`` passed
    with a perfect tool-sequence score when the run then also called ``rot13``, so ``eval``
    exited 0 for a run that called a tool its fixture never expected.
    """

    scenario = EvalScenario(
        scenario_id="echo_only",
        goal="Echo a confirmation token",
        scripted_responses=("TOOL:echo:ready", "TOOL:rot13:ready", "DONE: echoed ready"),
        expected_tools=("echo",),
        expected_answer_contains="echoed",
        max_steps=8,
    )

    report = EvaluationHarness((scenario,)).run(root=tmp_path, event_log_dir=tmp_path / "logs")
    score = report.scenarios[0]

    assert (score.actual_tools, score.answer_score, score.details["state"]) == (("echo", "rot13"), 1.0, "succeeded")
    assert (score.passed, score.tool_sequence_score, report.pass_rate) == (False, 0.5, 0.0)


@pytest.mark.parametrize(
    ("first_tool", "second_tool", "second_passes"),
    [("echo", "rot13", False), ("rot13", "echo", True)],
    ids=["regression-must-fail", "fix-must-pass"],
)
def test_rerun_into_the_same_log_dir_scores_only_the_new_run(
    tmp_path: Path,
    first_tool: str,
    second_tool: str,
    second_passes: bool,
) -> None:
    """Re-running eval into the same ``event_log_dir`` scores only the run it just executed.

    Each scenario used its id as the run id in ``<event_log_dir>/<scenario_id>.sqlite``, so a
    second ``eval`` appended to the earlier run and scored that run's tool calls first. A
    regression that calls the wrong tool still passed, and a fixed scenario kept failing
    until the log directory was deleted.
    """

    def evaluate(tool: str) -> ScenarioScore:
        scenario = EvalScenario(
            scenario_id="echo_check",
            goal="Echo a confirmation token",
            scripted_responses=(f"TOOL:{tool}:ready", "DONE: echoed ready"),
            expected_tools=("echo",),
            expected_answer_contains="echoed",
            max_steps=5,
        )
        return EvaluationHarness((scenario,)).run(root=tmp_path, event_log_dir=tmp_path / "logs").scenarios[0]

    first = evaluate(first_tool)
    second = evaluate(second_tool)

    assert (second.passed, second.actual_tools) == (second_passes, (second_tool,))
    assert first.passed is not second_passes
    log = SQLiteEventLog(tmp_path / "logs" / "echo_check.sqlite")
    try:
        runs = [event.run_id for event in log.list_events() if event.event_type == "run_created"]
    finally:
        log.close()
    assert sorted(runs) == sorted([first.details["run_id"], second.details["run_id"]])
    assert all(run_id.startswith("echo_check-") for run_id in runs)
