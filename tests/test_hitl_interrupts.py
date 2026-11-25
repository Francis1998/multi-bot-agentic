"""Tests for durable human-in-the-loop approval interrupts in the runner."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest

from multi_bot_agentic.approval import (
    ApprovalDecision,
    ApprovalError,
    AwaitingApprovalError,
    argument_preview,
    collect_interrupts,
    decide_interrupt,
    paused_interrupt,
    validate_edited_arguments,
)
from multi_bot_agentic.checkpoint import load_latest_checkpoint
from multi_bot_agentic.event_log import EventRecord, SQLiteEventLog
from multi_bot_agentic.fork import ForkError, build_history, plan_fork
from multi_bot_agentic.lifecycle import InvalidTransitionError, RunStateMachine
from multi_bot_agentic.llm.fake import FakeLLMAdapter
from multi_bot_agentic.models import EventType, RunState, ToolInvocation, ToolResult
from multi_bot_agentic.runner import AgentRunner
from multi_bot_agentic.safety import SafetyPolicy, parse_approval_patterns
from multi_bot_agentic.tracing import parse_run, render_mermaid

GOAL = "Create a launch checklist"


class SpyTool:
    """Checklist stand-in that records every execution."""

    name = "checklist"
    description = "records calls"

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        self.calls.append(dict(invocation.arguments))
        return ToolResult(tool_name="checklist", ok=True, content=f"ran: {invocation.arguments['text']}")


@pytest.fixture()
def event_log(tmp_path: Path) -> Iterator[SQLiteEventLog]:
    log = SQLiteEventLog(tmp_path / "runs.sqlite")
    yield log
    log.close()


def _runner(event_log: SQLiteEventLog, spy: SpyTool, **policy: object) -> AgentRunner:
    settings: dict[str, object] = {
        "allowed_tools": frozenset({"checklist"}),
        "require_approval": frozenset({"checklist"}),
    }
    settings.update(policy)
    return AgentRunner(FakeLLMAdapter(), event_log, {"checklist": spy}, SafetyPolicy(**settings))  # type: ignore[arg-type]


def _types(event_log: SQLiteEventLog, run_id: str) -> list[str]:
    return [event.event_type for event in event_log.list_events(run_id)]


def test_gated_tool_call_pauses_durably_without_executing(event_log: SQLiteEventLog) -> None:
    spy = SpyTool()
    result = _runner(event_log, spy).run(GOAL, run_id="r")

    assert result.state is RunState.AWAITING_APPROVAL
    assert result.steps == 1
    assert spy.calls == []
    events = event_log.list_events("r")
    assert events[0].payload["require_approval"] == ["checklist"]
    assert [event.event_type for event in events[-4:]] == ["decision", "state_transition", "interrupt", "checkpoint"]
    assert events[-3].payload == {"from": "deciding", "to": "awaiting_approval"}
    interrupt = events[-2].payload
    assert interrupt["tool"] == "checklist"
    assert interrupt["step"] == 2
    assert interrupt["bot"] is None
    assert interrupt["arguments"] == {"text": GOAL}
    assert interrupt["arguments_preview"] == '{"text": "Create a launch checklist"}'
    assert interrupt["rationale"]["rule_id"] == "model.requested-tool"
    assert interrupt["policy"] == ["checklist"]
    checkpoint = load_latest_checkpoint(event_log, "r")
    assert checkpoint is not None
    assert checkpoint.interrupt_id == interrupt["interrupt_id"] == result.interrupt.interrupt_id  # type: ignore[union-attr]
    assert checkpoint.state is RunState.AWAITING_APPROVAL
    assert checkpoint.step == 1
    assert checkpoint.require_approval == ("checklist",)


def test_ungated_runs_are_unchanged(event_log: SQLiteEventLog) -> None:
    spy = SpyTool()
    result = _runner(event_log, spy, require_approval=frozenset()).run(GOAL, run_id="plain")

    assert result.state is RunState.SUCCEEDED
    assert len(spy.calls) == 1
    assert "require_approval" not in event_log.list_events("plain")[0].payload
    assert "interrupt" not in _types(event_log, "plain")


def test_resume_refuses_an_undecided_interrupt_and_writes_nothing(event_log: SQLiteEventLog) -> None:
    spy = SpyTool()
    runner = _runner(event_log, spy)
    runner.run(GOAL, run_id="r")
    before = len(event_log.list_events("r"))

    with pytest.raises(AwaitingApprovalError, match="awaiting approval of interrupt int-"):
        runner.resume("r")

    assert len(event_log.list_events("r")) == before
    assert spy.calls == []


def test_approved_call_with_edited_arguments_runs_exactly_once(event_log: SQLiteEventLog) -> None:
    spy = SpyTool()
    runner = _runner(event_log, spy)
    paused = runner.run(GOAL, run_id="r")
    record = decide_interrupt(
        event_log,
        paused.interrupt.interrupt_id,  # type: ignore[union-attr]
        ApprovalDecision.APPROVED,
        decided_by="alice",
        reason="looks safe",
        arguments={"text": "Edited goal"},
    )
    assert record.status == "approved"
    assert record.decision is not None and record.decision.args_edited

    result = runner.resume("r")

    assert result.state is RunState.SUCCEEDED
    assert spy.calls == [{"text": "Edited goal"}]
    (requested,) = [
        event
        for event in event_log.list_events("r")
        if event.payload.get("action") == "call_tool" and event.event_type == "action_requested"
    ]
    assert requested.payload["payload"] == {"text": "Edited goal"}
    assert requested.payload["interrupt_id"] == record.interrupt_id
    again = runner.resume("r")
    assert again.already_finished
    assert len(spy.calls) == 1
    (final,) = collect_interrupts(event_log.list_events("r"))
    assert final.executed and final.status == "approved"
    assert final.to_dict()["resumed"] is True


def test_rejected_call_is_fed_back_and_the_model_replans(event_log: SQLiteEventLog) -> None:
    spy = SpyTool()
    runner = _runner(event_log, spy)
    runner.run(GOAL, run_id="r")
    decide_interrupt(event_log, None, ApprovalDecision.REJECTED, decided_by="bob", reason="too risky", run_id="r")

    result = runner.resume("r")

    assert result.state is RunState.SUCCEEDED
    assert result.answer == "re-planned without checklist after a human rejected it (too risky)"
    assert spy.calls == []
    observations = [event.payload for event in event_log.list_events("r") if event.event_type == "observation"]
    assert any(item["source"] == "approval:checklist" and "too risky" in item["content"] for item in observations)
    rules = [
        event.payload["rationale"]["rule_id"] for event in event_log.list_events("r") if event.event_type == "decision"
    ]
    assert "approval.rejected-needs-replan" in rules
    steps = build_history(event_log.list_events("r")).steps
    assert [(item.step, item.outcome, item.forkable) for item in steps][2] == (2, "rejected by human", True)


def test_first_decision_wins_and_later_decisions_are_refused(event_log: SQLiteEventLog) -> None:
    runner = _runner(event_log, SpyTool())
    paused = runner.run(GOAL, run_id="r")
    interrupt_id = paused.interrupt.interrupt_id  # type: ignore[union-attr]
    decide_interrupt(event_log, interrupt_id, ApprovalDecision.APPROVED, decided_by="alice")

    with pytest.raises(ApprovalError, match="already approved by alice"):
        decide_interrupt(event_log, interrupt_id, ApprovalDecision.REJECTED, decided_by="bob", reason="no")
    assert _types(event_log, "r").count("approval_decision") == 1


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"decision": ApprovalDecision.PENDING}, "approved or rejected"),
        ({"decision": ApprovalDecision.REJECTED}, "needs --reason"),
        ({"decision": ApprovalDecision.REJECTED, "reason": "x", "arguments": {"text": "y"}}, "never runs"),
        ({"decision": ApprovalDecision.APPROVED, "decided_by": " "}, "--by"),
        ({"decision": ApprovalDecision.APPROVED, "reason": "x" * 1001}, "limit is 1000"),
    ],
)
def test_invalid_decisions_are_refused(event_log: SQLiteEventLog, kwargs: dict[str, object], message: str) -> None:
    paused = _runner(event_log, SpyTool()).run(GOAL, run_id="r")
    params: dict[str, object] = {"decided_by": "alice"} | kwargs
    decision = params.pop("decision")

    with pytest.raises(ApprovalError, match=message):
        decide_interrupt(event_log, paused.interrupt.interrupt_id, decision, **params)  # type: ignore[arg-type,union-attr]
    assert "approval_decision" not in _types(event_log, "r")


def test_unknown_and_unpaused_interrupts_are_refused(event_log: SQLiteEventLog) -> None:
    _runner(event_log, SpyTool(), require_approval=frozenset()).run(GOAL, run_id="done")

    with pytest.raises(ApprovalError, match="interrupt int-missing not found"):
        decide_interrupt(event_log, "int-missing", ApprovalDecision.APPROVED, decided_by="alice")
    with pytest.raises(ApprovalError, match="is not paused at an interrupt"):
        decide_interrupt(event_log, None, ApprovalDecision.APPROVED, decided_by="alice", run_id="done")
    with pytest.raises(ApprovalError, match="run nope not found"):
        decide_interrupt(event_log, None, ApprovalDecision.APPROVED, decided_by="alice", run_id="nope")


def test_cancellation_at_resume_cancels_without_executing(event_log: SQLiteEventLog, tmp_path: Path) -> None:
    spy = SpyTool()
    cancel_file = tmp_path / "cancel"
    runner = _runner(event_log, spy, cancellation_file=cancel_file)
    paused = runner.run(GOAL, run_id="r")
    cancel_file.write_text("stop", encoding="utf-8")

    result = runner.resume("r")

    assert result.state is RunState.CANCELLED
    assert spy.calls == []
    (record,) = collect_interrupts(event_log.list_events("r"))
    assert record.interrupt_id == paused.interrupt.interrupt_id  # type: ignore[union-attr]
    assert record.status == "expired"
    with pytest.raises(ApprovalError, match=r"expired"):
        decide_interrupt(event_log, record.interrupt_id, ApprovalDecision.APPROVED, decided_by="alice")


def test_resume_respects_a_smaller_step_budget(event_log: SQLiteEventLog) -> None:
    spy = SpyTool()
    paused = _runner(event_log, spy).run(GOAL, run_id="r")
    decide_interrupt(event_log, paused.interrupt.interrupt_id, ApprovalDecision.APPROVED, decided_by="a")  # type: ignore[union-attr]

    result = _runner(event_log, spy, max_steps=1).resume("r")

    assert result.state is RunState.FAILED
    assert "max_steps=1" in result.answer
    assert spy.calls == []


def test_a_concurrent_resume_never_executes_the_claimed_call(event_log: SQLiteEventLog) -> None:
    spy = SpyTool()
    runner = _runner(event_log, spy)
    paused = runner.run(GOAL, run_id="r")
    decide_interrupt(event_log, paused.interrupt.interrupt_id, ApprovalDecision.APPROVED, decided_by="a")  # type: ignore[union-attr]
    # Another process claimed the interrupt (its action_requested) and is still running the tool.
    event_log.append(
        "r",
        RunState.ACTING,
        EventType.ACTION_REQUESTED,
        {"action": "call_tool", "interrupt_id": paused.interrupt.interrupt_id},  # type: ignore[union-attr]
    )

    with pytest.raises(ApprovalError, match="never executed twice"):
        runner.resume("r")
    assert spy.calls == []


def test_a_crashed_resume_continues_from_the_recorded_result(event_log: SQLiteEventLog) -> None:
    spy = SpyTool()
    runner = _runner(event_log, spy)
    paused = runner.run(GOAL, run_id="r")
    interrupt_id = paused.interrupt.interrupt_id  # type: ignore[union-attr]
    decide_interrupt(event_log, interrupt_id, ApprovalDecision.APPROVED, decided_by="a")
    # A resume executed the tool and crashed before its checkpoint.
    event_log.append("r", RunState.ACTING, EventType.ACTION_REQUESTED, {"interrupt_id": interrupt_id})
    event_log.append(
        "r",
        RunState.ACTING,
        EventType.ACTION_RESULT,
        {"kind": "tool", "tool": "checklist", "ok": True, "content": "ran once", "interrupt_id": interrupt_id},
    )

    result = runner.resume("r")

    assert result.state is RunState.SUCCEEDED
    assert spy.calls == []


def test_claim_is_atomic(event_log: SQLiteEventLog) -> None:
    def refuse(events: list[EventRecord]) -> None:
        raise ApprovalError("taken")

    with pytest.raises(ApprovalError, match="taken"):
        event_log.append_guarded("r", [(RunState.ACTING, EventType.ACTION_REQUESTED, {})], refuse)
    assert event_log.list_events("r") == []
    (record,) = event_log.append_guarded("r", [(RunState.ACTING, EventType.ACTION_REQUESTED, {})], lambda events: None)
    assert record.seq == 1


def test_recorded_policy_survives_resume_and_is_inherited_by_forks(event_log: SQLiteEventLog) -> None:
    spy = SpyTool()
    _runner(event_log, spy).run(GOAL, run_id="r")
    ungated = _runner(event_log, spy, require_approval=frozenset())

    with pytest.raises(AwaitingApprovalError):
        ungated.resume("r")
    plan = plan_fork(event_log, "r", 1, "f", provider="fake", policy=ungated.safety_policy)
    assert plan.require_approval == ("checklist",)
    assert plan.to_dict()["next_decision"]["needs_approval"] is True
    forked = ungated.fork("r", 1, "f")
    assert forked.state is RunState.AWAITING_APPROVAL
    assert spy.calls == []


def test_paused_step_is_listed_but_not_forkable(event_log: SQLiteEventLog) -> None:
    _runner(event_log, SpyTool()).run(GOAL, run_id="r")
    history = build_history(event_log.list_events("r"))

    assert history.final_state == "awaiting_approval"
    assert history.steps[-1].outcome == "approval pending"
    assert history.forkable_steps() == (0, 1)
    with pytest.raises(ForkError, match="paused awaiting human approval"):
        plan_fork(event_log, "r", 2, "f", provider="fake", policy=SafetyPolicy())


def test_trace_shows_the_interrupt_the_decision_and_the_resume(event_log: SQLiteEventLog) -> None:
    runner = _runner(event_log, SpyTool())
    paused = runner.run(GOAL, run_id="r")
    timeline = parse_run(event_log.list_events("r"))
    assert timeline.final_state == "awaiting_approval"
    assert "paused: awaiting human approval" in render_mermaid(event_log.list_events("r"))

    decide_interrupt(event_log, paused.interrupt.interrupt_id, ApprovalDecision.APPROVED, decided_by="a")  # type: ignore[union-attr]
    runner.resume("r")
    diagram = render_mermaid(event_log.list_events("r"))

    assert "O->>H: approve checklist?" in diagram
    assert "H-->>O: approved" in diagram
    assert "resumed from checkpoint" in diagram
    assert parse_run(event_log.list_events("r")).final_state == "succeeded"


def test_paused_interrupt_and_status_helpers(event_log: SQLiteEventLog) -> None:
    _runner(event_log, SpyTool()).run(GOAL, run_id="r")
    record = paused_interrupt(event_log.list_events("r"))

    assert record is not None and record.status == "pending" and record.paused
    assert record.effective_arguments == {"text": GOAL}


def test_lifecycle_allows_pausing_and_both_ways_out() -> None:
    for after in (RunState.ACTING, RunState.OBSERVING, RunState.CANCELLED, RunState.FAILED):
        machine = RunStateMachine(RunState.DECIDING)
        machine.transition_to(RunState.AWAITING_APPROVAL)
        machine.transition_to(after)
    with pytest.raises(InvalidTransitionError):
        RunStateMachine(RunState.AWAITING_APPROVAL).transition_to(RunState.SUCCEEDED)
    with pytest.raises(InvalidTransitionError):
        RunStateMachine(RunState.ACTING).transition_to(RunState.AWAITING_APPROVAL)


def test_policy_patterns_and_parsing() -> None:
    policy = SafetyPolicy(require_approval=parse_approval_patterns(["check*, mcp__*", "", "json_format"]))

    assert policy.require_approval == frozenset({"check*", "mcp__*", "json_format"})
    assert policy.requires_approval("checklist")
    assert policy.requires_approval("mcp__notes__search_notes")
    assert not policy.requires_approval("echo")
    assert not replace(policy, require_approval=frozenset()).requires_approval("checklist")


@pytest.mark.parametrize(
    ("edited", "message"),
    [
        (["x"], "must be a JSON object, got array"),
        ({"query": "x"}, "exactly the keys of the requested call \\(text\\), got query"),
        ({"text": 3}, "'text' must be a string, got number"),
        ({"text": "x" * 70_000}, "the limit is 65536"),
        ({"text": float("nan")}, "must be a string, got number"),
    ],
)
def test_edited_arguments_keep_the_call_shape(edited: object, message: str) -> None:
    with pytest.raises(ApprovalError, match=message):
        validate_edited_arguments({"text": "original"}, edited)
    assert validate_edited_arguments({"text": "a"}, {"text": "b"}) == {"text": "b"}


def test_argument_preview_redacts_and_truncates() -> None:
    preview = argument_preview(
        {"api_key": "sk-abcdefghijklmnopqrstuvwxyz", "text": "mail ops@example.com " + "x" * 400}
    )

    assert "sk-abc" not in preview and "ops@example.com" not in preview
    assert '"api_key": "[REDACTED]"' in preview and "[EMAIL]" in preview
    assert preview.endswith("...[truncated]") and len(preview) <= 240 + len("...[truncated]")
