"""Runner, resume, and fork behaviour of runs with an output schema (offline, scripted providers)."""

from __future__ import annotations

import contextlib
import sqlite3
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

import pytest

from multi_bot_agentic.cli import output_report
from multi_bot_agentic.decision import DeterministicDecisionEngine
from multi_bot_agentic.event_log import EventRecord, SQLiteEventLog
from multi_bot_agentic.fork import ForkError, plan_fork
from multi_bot_agentic.lifecycle import InvalidTransitionError, RunStateMachine
from multi_bot_agentic.models import ModelOutput, ModelRequest, Observation, RunState
from multi_bot_agentic.runner import AgentRunner, recorded_outcome
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.structured_output import (
    CORRECTION_SOURCE,
    MAX_ANSWER_CHARS,
    OutputContract,
    OutputSchema,
)
from multi_bot_agentic.tracing import build_trace

TITLE_SCHEMA = {"type": "object", "required": ["title"], "properties": {"title": {"type": "string", "minLength": 2}}}
NAME_SCHEMA = {"type": "object", "required": ["name"]}


class Scripted:
    """Provider that replays texts (or raises an exception) and records every request."""

    provider_name = "fake"

    def __init__(self, *replies: str | BaseException) -> None:
        self.replies = list(replies)
        self.requests: list[ModelRequest] = []

    def complete(self, request: ModelRequest, timeout_seconds: float) -> ModelOutput:
        del timeout_seconds
        self.requests.append(request)
        reply = self.replies.pop(0) if self.replies else "DONE: out of replies"
        if isinstance(reply, BaseException):
            raise reply
        return ModelOutput(provider=self.provider_name, text=reply)


def _runner(log: SQLiteEventLog, provider: Scripted, max_steps: int = 6) -> AgentRunner:
    return AgentRunner(
        provider=provider,
        event_log=log,
        tools={},
        safety_policy=SafetyPolicy(max_steps=max_steps, allowed_tools=frozenset()),
    )


def _contract(schema: Any = TITLE_SCHEMA, retries: int = 2) -> OutputContract:
    return OutputContract(schema=OutputSchema.from_value(schema, source="schema.json"), retries=retries)


def _events(log: SQLiteEventLog, run_id: str, kind: str | None = None) -> list[EventRecord]:
    return [event for event in log.list_events(run_id) if kind is None or event.event_type == kind]


@pytest.fixture
def log(tmp_path: Path) -> Iterator[SQLiteEventLog]:
    event_log = SQLiteEventLog(tmp_path / "runs.sqlite")
    yield event_log
    event_log.close()


def test_invalid_answer_gets_a_correction_round_then_validates(log: SQLiteEventLog) -> None:
    provider = Scripted("DONE: here is the plan", 'DONE: ```json\n{"title": "Launch"}\n```')
    result = _runner(log, provider).run("Plan the launch", run_id="r", output_contract=_contract())

    assert result.state is RunState.SUCCEEDED and result.steps == 4
    assert result.output is not None and result.output.value == {"title": "Launch"}
    assert (result.output.attempt, result.output.source) == (2, "json_block")
    kinds = [event.event_type for event in _events(log, "r") if event.event_type not in {"observation", "checkpoint"}]
    assert kinds.count("output_validation_failed") == 1 and kinds.index("output_validation_failed") < kinds.index(
        "final_output"
    )
    failed = _events(log, "r", "output_validation_failed")[0]
    assert failed.state == "validating"
    assert failed.payload == {
        "attempt": 1,
        "max_attempts": 3,
        "errors": [
            "$: no JSON document found; reply with only the JSON document, or put it in one ```json fenced block"
        ],
        "schema_sha256": _contract().schema.sha256,
        "retry": True,
    }
    final = _events(log, "r", "final_output")[0].payload
    assert final["output"] == {"title": "Launch"} and final["attempt"] == 2 and final["bytes"] == 18
    correction = provider.requests[1].observations[-1]
    assert correction.source == CORRECTION_SOURCE
    assert correction.content.startswith("OUTPUT_INVALID: final answer attempt 1 of 3 failed validation")
    assert all(request.output_schema == TITLE_SCHEMA for request in provider.requests)
    assert all(request.max_output_chars == MAX_ANSWER_CHARS for request in provider.requests)
    decisions = [event.payload["rationale"]["rule_id"] for event in _events(log, "r", "decision")]
    assert decisions[2] == "output.invalid-needs-correction"
    created = _events(log, "r", "run_created")[0].payload
    assert created["output_contract"] == _contract().to_payload()


def test_exhausted_retries_end_in_output_invalid(log: SQLiteEventLog) -> None:
    provider = Scripted('DONE: {"title": 1}', 'DONE: {"title": "x"}')
    result = _runner(log, provider).run("Plan", run_id="r", output_contract=_contract(retries=1))

    assert result.state is RunState.OUTPUT_INVALID and result.steps == 4
    assert result.output_errors == ("$.title: expected at least 2 characters, got 1",)
    assert result.answer == "the final answer failed output validation after 2 attempts (1 error in the last answer)"
    failures = _events(log, "r", "output_validation_failed")
    assert [item.payload["retry"] for item in failures] == [True, False]
    assert failures[-1].payload["stop"] == "retries_exhausted"
    terminal = _events(log, "r")[-1]
    assert (terminal.event_type, terminal.state) == ("run_failed", "output_invalid")
    recorded = recorded_outcome(log, "r")
    assert recorded is not None and recorded.state is RunState.OUTPUT_INVALID
    assert recorded.output_errors == result.output_errors
    again = _runner(log, Scripted()).resume("r")
    assert again.already_finished and again.state is RunState.OUTPUT_INVALID


def test_a_correction_round_needs_two_steps(log: SQLiteEventLog) -> None:
    result = _runner(log, Scripted("DONE: nope"), max_steps=3).run("Plan", run_id="r", output_contract=_contract())

    assert result.state is RunState.OUTPUT_INVALID and result.steps == 2
    failure = _events(log, "r", "output_validation_failed")[0].payload
    assert (failure["retry"], failure["stop"]) == (False, "step_budget")
    assert "no steps are left for a correction round (raise --max-steps)" in result.answer


def test_runs_without_a_contract_are_unchanged(log: SQLiteEventLog) -> None:
    provider = Scripted("DONE: plain text")
    result = _runner(log, provider).run("Plan", run_id="r")

    assert result.state is RunState.SUCCEEDED and result.output is None and result.answer == "plain text"
    assert provider.requests[0].output_schema is None and provider.requests[0].max_output_chars == 2000
    assert not any(event.state == "validating" for event in _events(log, "r"))
    assert "output_contract" not in _events(log, "r", "run_created")[0].payload


def test_resume_enforces_the_recorded_contract_and_counts_failed_answers(log: SQLiteEventLog) -> None:
    with pytest.raises(KeyboardInterrupt):
        _runner(log, Scripted("DONE: nope", KeyboardInterrupt())).run(
            "Plan", run_id="r", output_contract=_contract(retries=1)
        )
    assert recorded_outcome(log, "r") is None

    provider = Scripted('DONE: {"title": "Resumed"}')
    result = _runner(log, provider).resume("r")

    assert result.state is RunState.SUCCEEDED and not result.already_finished
    assert result.output is not None and result.output.attempt == 2
    assert provider.requests[0].output_schema == TITLE_SCHEMA


def test_resume_refuses_a_tampered_contract(log: SQLiteEventLog) -> None:
    with pytest.raises(KeyboardInterrupt):
        _runner(log, Scripted("DONE: nope", KeyboardInterrupt())).run("Plan", run_id="r", output_contract=_contract())
    connection = sqlite3.connect(log.path)
    with connection:
        connection.execute(
            "UPDATE events SET payload_json = replace(payload_json, '\"minLength\": 2', '\"minLength\": 1') "
            "WHERE run_id = 'r' AND event_type = 'run_created'"
        )
    connection.close()
    with pytest.raises(ValueError, match="does not match its sha256 digest"):
        _runner(log, Scripted()).resume("r")


def _failed_source(log: SQLiteEventLog, *replies: str, retries: int = 0, run_id: str = "src") -> None:
    result = _runner(log, Scripted(*replies)).run("Plan", run_id=run_id, output_contract=_contract(retries=retries))
    assert result.state is RunState.OUTPUT_INVALID


def test_fork_with_a_new_schema_revalidates_the_recorded_answer(log: SQLiteEventLog) -> None:
    _failed_source(log, 'DONE: {"name": "x"}')
    provider = Scripted()
    new_schema = OutputSchema.from_value(NAME_SCHEMA, source="name.json")
    result = _runner(log, provider).fork("src", 1, "fork", output_schema=new_schema)

    assert result.state is RunState.SUCCEEDED and provider.requests == []
    assert result.output is not None and result.output.value == {"name": "x"} and result.output.attempt == 1
    lineage = _events(log, "fork", "run_forked")[0].payload
    assert lineage["overrides"] == {"output_schema": {"schema_sha256": new_schema.sha256, "source": "name.json"}}
    assert lineage["output_contract"]["schema"] == NAME_SCHEMA


def test_fork_inherits_the_contract_and_its_failed_answers(log: SQLiteEventLog) -> None:
    _failed_source(log, "DONE: nope", "DONE: still nope", retries=1)
    provider = Scripted('DONE: {"title": "Fixed"}')
    result = _runner(log, provider).fork("src", 2, "fork")

    assert result.state is RunState.SUCCEEDED
    assert result.output is not None and result.output.attempt == 2
    assert provider.requests[0].output_schema == TITLE_SCHEMA
    lineage = _events(log, "fork", "run_forked")[0].payload
    assert lineage["overrides"] == {} and lineage["output_contract"] == _contract(retries=1).to_payload()


def test_fork_with_a_new_schema_does_not_count_answers_checked_against_the_old_one(log: SQLiteEventLog) -> None:
    _failed_source(log, "DONE: nope", "DONE: still nope", retries=1, run_id="rescue-src")
    new_schema = OutputSchema.from_value(NAME_SCHEMA, source="name.json")
    result = _runner(log, Scripted('DONE: {"name": "n"}')).fork("rescue-src", 2, "fork", output_schema=new_schema)

    assert result.state is RunState.SUCCEEDED and result.output is not None and result.output.attempt == 1
    assert len(_events(log, "fork", "output_validation_failed")) == 1
    report = output_report(log.list_events("fork"))
    assert report is not None and (report["attempts"], report["valid"]) == (1, True)


def test_fork_output_retries_override_and_errors(log: SQLiteEventLog) -> None:
    _failed_source(log, "DONE: nope")
    policy = SafetyPolicy(max_steps=6, allowed_tools=frozenset())
    plan = plan_fork(log, "src", 1, "fork", provider="fake", policy=policy, output_retries=3)
    assert plan.output_contract is not None and plan.output_contract.retries == 3
    assert plan.lineage["overrides"] == {"output_retries": 3}
    assert plan.to_dict()["output_contract"]["retries"] == 3
    _runner(log, Scripted("DONE: plain")).run("Plan", run_id="plain")
    with pytest.raises(ForkError, match="has no output schema"):
        plan_fork(log, "plain", 1, "fork2", provider="fake", policy=policy, output_retries=1)
    with pytest.raises(ForkError, match="between 0 and 10"):
        plan_fork(log, "src", 1, "fork3", provider="fake", policy=policy, output_retries=11)


def test_correction_observation_selects_a_model_call() -> None:
    engine = DeterministicDecisionEngine(provider_name="fake")
    observations = (
        Observation(source="user", content="Plan"),
        Observation(source="llm:fake", content="DONE: nope"),
        Observation(source=CORRECTION_SOURCE, content="OUTPUT_INVALID: ..."),
    )
    decision = engine.decide(observations, 2, SafetyPolicy(max_steps=6))
    assert (decision.action, decision.rationale.rule_id) == ("call_llm", "output.invalid-needs-correction")


@pytest.mark.parametrize(
    ("path", "allowed"),
    [
        ((RunState.OBSERVING, RunState.DECIDING, RunState.VALIDATING, RunState.OBSERVING), True),
        ((RunState.OBSERVING, RunState.DECIDING, RunState.VALIDATING, RunState.OUTPUT_INVALID), True),
        ((RunState.OBSERVING, RunState.DECIDING, RunState.VALIDATING, RunState.ACTING), False),
        (
            (RunState.OBSERVING, RunState.DECIDING, RunState.VALIDATING, RunState.OUTPUT_INVALID, RunState.OBSERVING),
            False,
        ),
    ],
)
def test_validating_and_output_invalid_transitions(path: Sequence[RunState], allowed: bool) -> None:
    machine = RunStateMachine()

    def move() -> None:
        for state in path:
            machine.transition_to(state)

    if allowed:
        move()
        assert machine.is_terminal() is (path[-1] is RunState.OUTPUT_INVALID)
    else:
        with pytest.raises(InvalidTransitionError):
            move()


def test_an_answer_that_cannot_be_stored_is_an_invalid_answer(log: SQLiteEventLog) -> None:
    result = _runner(log, Scripted("DONE: 1e400")).run("Plan", run_id="r", output_contract=_contract(retries=0))
    assert result.state is RunState.OUTPUT_INVALID
    assert result.output_errors and result.output_errors[0].startswith("$: ")


def _crash_after(monkeypatch: pytest.MonkeyPatch, log: SQLiteEventLog, event_type: str) -> None:
    """Make the first write to ``log`` after an ``event_type`` event raise KeyboardInterrupt, like a crash."""

    append, append_guarded = log.append, log.append_guarded
    state = {"seen": False, "crashed": False}

    def crash_if_due() -> None:
        if state["seen"] and not state["crashed"]:
            state["crashed"] = True
            raise KeyboardInterrupt

    def patched_append(run_id: str, run_state: RunState, kind: Any, payload: dict[str, Any]) -> EventRecord:
        crash_if_due()
        record = append(run_id, run_state, kind, payload)
        state["seen"] = state["seen"] or kind.value == event_type
        return record

    def patched_guarded(run_id: str, entries: Any, guard: Any = None) -> list[EventRecord]:
        crash_if_due()
        records = append_guarded(run_id, entries, guard)
        state["seen"] = state["seen"] or any(kind.value == event_type for _, kind, _ in entries)
        return records

    monkeypatch.setattr(log, "append", patched_append)
    monkeypatch.setattr(log, "append_guarded", patched_guarded)


def test_a_crash_after_a_failed_check_keeps_the_correction_round(
    log: SQLiteEventLog, monkeypatch: pytest.MonkeyPatch
) -> None:
    _crash_after(monkeypatch, log, "output_validation_failed")
    with contextlib.suppress(KeyboardInterrupt):
        _runner(log, Scripted("DONE: nope")).run("Plan", run_id="r", output_contract=_contract(retries=1))
    monkeypatch.undo()
    provider = Scripted('DONE: {"title": "Fixed"}')
    result = _runner(log, provider).resume("r")

    assert result.state is RunState.SUCCEEDED
    assert result.output is not None and result.output.attempt == 2
    assert provider.requests and provider.requests[0].observations[-1].source == CORRECTION_SOURCE
    assert len(_events(log, "r", "output_validation_failed")) == 1


def test_a_crash_after_a_valid_check_records_one_final_output(
    log: SQLiteEventLog, monkeypatch: pytest.MonkeyPatch
) -> None:
    _crash_after(monkeypatch, log, "final_output")
    try:
        _runner(log, Scripted('DONE: {"title": "Launch"}')).run("Plan", run_id="r", output_contract=_contract())
    except KeyboardInterrupt:
        monkeypatch.undo()
        _runner(log, Scripted()).resume("r")
    recorded = recorded_outcome(log, "r")
    assert recorded is not None and recorded.state is RunState.SUCCEEDED
    assert len(_events(log, "r", "final_output")) == 1


def _new_schema_fork(log: SQLiteEventLog, *replies: str | BaseException) -> RunState | None:
    """Fork a run that failed two answers under TITLE_SCHEMA after its correction step, with NAME_SCHEMA."""

    _failed_source(log, "DONE: nope", "DONE: still nope", retries=1, run_id="old")
    new_schema = OutputSchema.from_value(NAME_SCHEMA, source="name.json")
    try:
        return _runner(log, Scripted(*replies)).fork("old", 2, "fork", output_schema=new_schema).state
    except KeyboardInterrupt:
        return None


def test_report_shows_only_errors_of_the_forks_own_schema(log: SQLiteEventLog) -> None:
    assert _new_schema_fork(log, KeyboardInterrupt()) is None
    report = output_report(log.list_events("fork"))
    assert report is not None and (report["attempts"], report["valid"]) == (0, None)
    assert "errors" not in report


def test_trace_counts_only_checks_against_the_forks_own_schema(log: SQLiteEventLog) -> None:
    assert _new_schema_fork(log, 'DONE: {"name": "n"}') is RunState.SUCCEEDED
    root = build_trace(log.list_events("fork")).spans[0]
    assert root.attributes["multi_bot_agentic.output.attempts"] == 1
    assert root.attributes["multi_bot_agentic.output.valid"] is True
    # The inherited check against the replaced schema stays visible as its own span event.
    checks = [event.attributes for event in root.events if event.name == "multi_bot_agentic.output.validation"]
    assert [check["multi_bot_agentic.output.valid"] for check in checks] == [False, True]
    assert [check["multi_bot_agentic.output.schema_sha256"] for check in checks] == [
        _contract().schema.sha256,
        OutputSchema.from_value(NAME_SCHEMA).sha256,
    ]
