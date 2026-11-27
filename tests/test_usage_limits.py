"""Usage accounting and run-level usage limits: events, checkpoints, resume, fork, HITL, CLI, report, trace, eval."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from _pytest.capture import CaptureFixture
from _pytest.monkeypatch import MonkeyPatch

from multi_bot_agentic.approval import ApprovalDecision, decide_interrupt
from multi_bot_agentic.checkpoint import load_latest_checkpoint
from multi_bot_agentic.cli import build_run_report, main
from multi_bot_agentic.eval import EvalScenario, EvaluationHarness, load_scenario
from multi_bot_agentic.event_log import EventRecord, SQLiteEventLog
from multi_bot_agentic.fork import build_history
from multi_bot_agentic.llm.claude_code_cli import ClaudeCodeCLIAdapter
from multi_bot_agentic.llm.fake import FakeLLMAdapter
from multi_bot_agentic.llm.gemini import GeminiAdapter
from multi_bot_agentic.llm.openai import OpenAIAdapter
from multi_bot_agentic.models import EventType, ModelOutput, ModelRequest, RunState, ToolInvocation, ToolResult, Usage
from multi_bot_agentic.runner import AgentRunner
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tracing import build_trace, render_mermaid
from multi_bot_agentic.usage import UsageLimits, UsageTotals

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


class _Crash(BaseException):
    """Simulates the process dying: the runner does not catch it."""


class CrashingProvider:
    """Fake provider that dies (like a killed process) on its ``crash_on``-th call."""

    provider_name = "fake"

    def __init__(self, crash_on: int) -> None:
        self.inner = FakeLLMAdapter()
        self.crash_on = crash_on
        self.calls = 0

    def complete(self, request: ModelRequest, timeout_seconds: float) -> ModelOutput:
        self.calls += 1
        if self.calls >= self.crash_on:
            raise _Crash
        return self.inner.complete(request, timeout_seconds)


class CostOnlyProvider:
    """Provider that reports its own cost but no token usage."""

    provider_name = "claude_code"

    def __init__(self) -> None:
        self.replies = iter(["TOOL:checklist:ship", "DONE: shipped"])

    def complete(self, request: ModelRequest, timeout_seconds: float) -> ModelOutput:
        return ModelOutput(provider=self.provider_name, text=next(self.replies), cost_usd=0.25)


class PartialUsageProvider:
    """Provider that reports some token counters but not others."""

    provider_name = "fake"

    def __init__(self, usage: Usage) -> None:
        self.usage = usage
        self.replies = iter(["TOOL:checklist:ship", "DONE: shipped"])

    def complete(self, request: ModelRequest, timeout_seconds: float) -> ModelOutput:
        return ModelOutput(provider=self.provider_name, text=next(self.replies), usage=self.usage, model="fake")


class UnmeteredProvider:
    """Provider that reports no usage, like Claude Code's plain-text output."""

    provider_name = "claude_code"

    def __init__(self) -> None:
        self.replies = iter(["TOOL:checklist:ship", "DONE: shipped"])

    def complete(self, request: ModelRequest, timeout_seconds: float) -> ModelOutput:
        return ModelOutput(provider=self.provider_name, text=next(self.replies))


@pytest.fixture()
def event_log(tmp_path: Path) -> Iterator[SQLiteEventLog]:
    log = SQLiteEventLog(tmp_path / "runs.sqlite")
    yield log
    log.close()


def _runner(
    event_log: SQLiteEventLog,
    spy: SpyTool | None = None,
    *,
    limits: UsageLimits | None = None,
    provider: object | None = None,
    approval: frozenset[str] = frozenset(),
) -> AgentRunner:
    policy = SafetyPolicy(
        allowed_tools=frozenset({"checklist"}), require_approval=approval, usage_limits=limits or UsageLimits()
    )
    return AgentRunner(provider or FakeLLMAdapter(), event_log, {"checklist": spy or SpyTool()}, policy)  # type: ignore[arg-type]


def _of(event_log: SQLiteEventLog, run_id: str, kind: EventType) -> list[EventRecord]:
    return [event for event in event_log.list_events(run_id) if event.event_type == kind.value]


def test_every_model_call_records_an_llm_usage_event_before_its_result(event_log: SQLiteEventLog) -> None:
    result = _runner(event_log).run(GOAL, run_id="r")

    events = event_log.list_events("r")
    usage = _of(event_log, "r", EventType.LLM_USAGE)
    assert len(usage) == 2
    first = usage[0].payload
    assert (first["bot"], first["provider"], first["model"]) == (None, "fake", "fake")
    assert first["usage"]["requests"] == 1 and first["usage"]["input_tokens"] > 0
    assert (first["cost"]["usd"], first["cost"]["source"]) == (0.0, "price_table")
    assert first["priced_at"] == datetime.now(timezone.utc).date().isoformat()
    assert [item.payload["totals"]["requests"] for item in usage] == [1, 2]
    following = events[events.index(usage[0]) + 1]
    assert (following.event_type, following.payload["kind"]) == ("action_result", "llm")
    assert result.usage == UsageTotals.from_events(events)
    assert result.usage is not None and result.usage.total_tokens == sum(
        item.payload["usage"]["total_tokens"] for item in usage
    )


def test_usage_limits_are_recorded_and_checkpointed(event_log: SQLiteEventLog) -> None:
    limits = UsageLimits(max_requests=5, max_cost_usd=1.5)
    _runner(event_log, limits=limits).run(GOAL, run_id="r")

    created = event_log.list_events("r")[0]
    assert created.payload["usage_limits"] == {"max_requests": 5, "max_cost_usd": 1.5}
    snapshot = load_latest_checkpoint(event_log, "r")
    assert snapshot is not None and snapshot.usage_limits == limits


def test_before_call_limit_stops_without_recording_the_blocked_call(event_log: SQLiteEventLog) -> None:
    """max_requests=1: the second model call is never made, and step 2 stays a clean fork point."""

    spy = SpyTool()
    result = _runner(event_log, spy, limits=UsageLimits(max_requests=1)).run(GOAL, run_id="r")

    assert (result.state, result.steps) == (RunState.USAGE_LIMIT_EXCEEDED, 2)
    assert result.usage_limit is not None
    assert (result.usage_limit.limit, result.usage_limit.phase) == ("max_requests", "before_call")
    assert result.answer == "stopped: the next model call would exceed max_requests=1 (requests=1)"
    events = event_log.list_events("r")
    assert [event.event_type for event in events[-3:]] == ["state_transition", "usage_limit_exceeded", "checkpoint"]
    stop = events[-2].payload
    assert (stop["limit"], stop["value"], stop["cap"], stop["phase"], stop["step"]) == (
        "max_requests",
        1,
        1,
        "before_call",
        3,
    )
    assert [event.payload["action"] for event in _of(event_log, "r", EventType.DECISION)][-1] == "call_tool"
    assert (events[-1].payload["step"], events[-1].state) == (2, "usage_limit_exceeded")
    assert len(_of(event_log, "r", EventType.LLM_USAGE)) == 1 and len(spy.calls) == 1
    history = build_history(events)
    assert history.final_state == "usage_limit_exceeded" and history.forkable_steps() == (0, 1, 2)


@pytest.mark.parametrize(
    ("limits", "limit"),
    [
        (UsageLimits(max_input_tokens=1), "max_input_tokens"),
        (UsageLimits(max_output_tokens=1), "max_output_tokens"),
        (UsageLimits(max_total_tokens=1), "max_total_tokens"),
    ],
)
def test_after_call_limits_keep_the_output_and_a_higher_limit_resumes(
    event_log: SQLiteEventLog, limits: UsageLimits, limit: str
) -> None:
    spy = SpyTool()
    stopped = _runner(event_log, spy, limits=limits).run(GOAL, run_id="r")

    assert stopped.state is RunState.USAGE_LIMIT_EXCEEDED and stopped.steps == 1
    assert stopped.usage_limit is not None and (stopped.usage_limit.limit, stopped.usage_limit.phase) == (
        limit,
        "after_call",
    )
    snapshot = load_latest_checkpoint(event_log, "r")
    assert snapshot is not None and snapshot.observations[-1].source == "llm:fake"
    assert spy.calls == []

    raised = UsageLimits(**{limit: 100_000})
    resumed = _runner(event_log, spy, limits=raised).resume("r")

    assert (resumed.state, resumed.answer) == (RunState.SUCCEEDED, "synthesized plan from 3 observations")
    assert len(_of(event_log, "r", EventType.LLM_USAGE)) == 2 and len(spy.calls) == 1
    transitions = [event.payload for event in _of(event_log, "r", EventType.STATE_TRANSITION)]
    assert {"from": "usage_limit_exceeded", "to": "observing"} in transitions


def test_cost_limit_uses_the_price_table(event_log: SQLiteEventLog) -> None:
    """The fake provider priced as GPT-6.2 Sol rehearses a cost limit offline."""

    provider = FakeLLMAdapter(model="gpt-6.2-sol")
    result = _runner(event_log, limits=UsageLimits(max_cost_usd=0.0001), provider=provider).run(GOAL, run_id="r")

    assert result.state is RunState.USAGE_LIMIT_EXCEEDED
    assert result.usage_limit is not None and result.usage_limit.limit == "max_cost_usd"
    cost = _of(event_log, "r", EventType.LLM_USAGE)[0].payload["cost"]
    assert cost["source"] == "price_table" and cost["rate"]["model"] == "gpt-6.2-sol"
    assert result.usage is not None and result.usage.cost_usd is not None and result.usage.cost_usd > 0.0001


def test_zero_token_budget_blocks_the_first_call(event_log: SQLiteEventLog) -> None:
    result = _runner(event_log, limits=UsageLimits(max_total_tokens=0)).run(GOAL, run_id="r")

    assert (result.state, result.steps) == (RunState.USAGE_LIMIT_EXCEEDED, 0)
    assert result.usage == UsageTotals()
    assert _of(event_log, "r", EventType.LLM_USAGE) == []


def test_resume_while_still_over_the_limit_writes_nothing(event_log: SQLiteEventLog) -> None:
    """The recorded limit stays in force: resuming without raising it repeats the stop, idempotently."""

    _runner(event_log, limits=UsageLimits(max_total_tokens=1)).run(GOAL, run_id="r")
    before = len(event_log.list_events("r"))

    again = _runner(event_log).resume("r")

    assert (again.state, again.still_stopped) == (RunState.USAGE_LIMIT_EXCEEDED, True)
    assert again.usage_limit is not None and again.usage_limit.limit == "max_total_tokens"
    assert len(event_log.list_events("r")) == before


def test_unmeasured_usage_cannot_satisfy_a_limit_until_it_is_reset(event_log: SQLiteEventLog) -> None:
    limits = UsageLimits(max_total_tokens=1000)
    provider = UnmeteredProvider()
    stopped = _runner(event_log, limits=limits, provider=provider).run(GOAL, run_id="r")

    assert stopped.usage_limit is not None and stopped.usage_limit.value is None
    assert stopped.answer == (
        "stopped: max_total_tokens=1000 cannot be enforced: 1 model call(s) reported no token usage"
    )
    record = _of(event_log, "r", EventType.LLM_USAGE)[0].payload
    assert record["usage"] is None and record["cost"]["usd"] is None

    resumed = _runner(event_log, provider=provider).resume("r", reset_usage_limits=True)
    assert resumed.state is RunState.SUCCEEDED
    assert resumed.usage is not None and (resumed.usage.unmeasured_requests, resumed.usage.total_tokens) == (2, None)


def test_resume_continues_the_totals_from_the_log(event_log: SQLiteEventLog) -> None:
    _runner(event_log, limits=UsageLimits(max_requests=1)).run(GOAL, run_id="r")

    resumed = _runner(event_log, limits=UsageLimits(max_requests=2)).resume("r")

    assert resumed.state is RunState.SUCCEEDED
    assert resumed.usage is not None and resumed.usage.requests == 2
    assert _of(event_log, "r", EventType.LLM_USAGE)[-1].payload["totals"]["requests"] == 2


def test_fork_starts_from_the_totals_at_its_fork_point(event_log: SQLiteEventLog) -> None:
    _runner(event_log).run(GOAL, run_id="source")
    source_first_call = _of(event_log, "source", EventType.LLM_USAGE)[0].payload["usage"]

    blocked = _runner(event_log, limits=UsageLimits(max_requests=1)).fork("source", 1, "fork")

    assert blocked.state is RunState.USAGE_LIMIT_EXCEEDED
    assert blocked.usage is not None and blocked.usage.requests == 1
    assert blocked.usage.total_tokens == source_first_call["total_tokens"]
    assert blocked.usage_limit is not None and blocked.usage_limit.phase == "before_call"

    finished = _runner(event_log, limits=UsageLimits(max_requests=3)).fork("source", 1, "fork-2")
    assert finished.state is RunState.SUCCEEDED and finished.usage is not None and finished.usage.requests == 2


def test_an_approved_tool_never_runs_again_after_a_limit_stop(event_log: SQLiteEventLog) -> None:
    spy = SpyTool()
    paused = _runner(event_log, spy, limits=UsageLimits(max_requests=1), approval=frozenset({"checklist"})).run(
        GOAL, run_id="r"
    )
    assert paused.state is RunState.AWAITING_APPROVAL
    decide_interrupt(event_log, None, ApprovalDecision.APPROVED, decided_by="alice", run_id="r")

    stopped = _runner(event_log, spy, approval=frozenset({"checklist"})).resume("r")
    assert stopped.state is RunState.USAGE_LIMIT_EXCEEDED and len(spy.calls) == 1

    finished = _runner(event_log, spy, limits=UsageLimits(max_requests=2)).resume("r")
    assert finished.state is RunState.SUCCEEDED
    assert len(spy.calls) == 1
    tool_results = [event for event in _of(event_log, "r", EventType.ACTION_RESULT) if event.payload["kind"] == "tool"]
    assert len(tool_results) == 1


def _cli(capsys: CaptureFixture[str], *argv: str) -> tuple[int, dict[str, object], str]:
    code = main(list(argv))
    captured = capsys.readouterr()
    return code, json.loads(captured.out), captured.err


def test_cli_stops_with_exit_code_5_and_resumes_with_a_higher_limit(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    log = str(tmp_path / "cli.sqlite")
    common = ("--event-log", log, "--run-id", "c")

    code, payload, err = _cli(capsys, "run", "--goal", GOAL, "--provider", "fake", *common, "--max-total-tokens", "100")

    assert (code, payload["state"]) == (5, "usage_limit_exceeded")
    assert payload["usage_limit"]["limit"] == "max_total_tokens"  # type: ignore[index]
    assert payload["usage"]["requests"] == 2  # type: ignore[index]
    assert "note: run c stopped at a usage limit: total_tokens=" in err
    assert f"resume --run-id c --event-log {log} and raise it with --max-total-tokens <N>" in err

    code, payload, _ = _cli(capsys, "resume", *common)
    assert (code, payload["state"], payload["resumed"]) == (5, "usage_limit_exceeded", False)
    code, payload, _ = _cli(capsys, "resume", *common, "--max-total-tokens", "100000")
    assert (code, payload["state"], payload["resumed"]) == (0, "succeeded", True)


@pytest.mark.parametrize("flag", ["--max-requests", "--max-total-tokens", "--max-cost-usd"])
def test_cli_rejects_negative_limits(flag: str, tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as raised:
        main(["run", "--goal", GOAL, "--event-log", str(tmp_path / "x.sqlite"), flag, "-1"])

    assert raised.value.code == 2
    assert ">= 0" in capsys.readouterr().err
    assert not (tmp_path / "x.sqlite").exists()


def test_cli_refuses_an_invalid_price_file(
    tmp_path: Path, monkeypatch: MonkeyPatch, capsys: CaptureFixture[str]
) -> None:
    prices = tmp_path / "prices.json"
    prices.write_text('{"models": {"gemini-3.8-flash": {"input": "cheap", "output": 1}}}')
    monkeypatch.setenv("MULTIBOT_PRICES_FILE", str(prices))

    code = main(["run", "--goal", GOAL, "--provider", "fake", "--event-log", str(tmp_path / "x.sqlite")])

    assert code == 2
    assert "gemini-3.8-flash.input must be a number >= 0" in capsys.readouterr().err
    assert not (tmp_path / "x.sqlite").exists()


def test_report_shows_usage_per_run_bot_and_model_and_counts_inherited_calls_once(
    event_log: SQLiteEventLog,
) -> None:
    _runner(event_log).run(GOAL, run_id="source")
    _runner(event_log).fork("source", 1, "fork")

    report = build_run_report(event_log.list_events())
    runs = {run["run_id"]: run for run in report["runs"]}
    source, fork = runs["source"], runs["fork"]
    assert source["usage"]["requests"] == 2
    assert source["usage"]["by_model"] == [
        {"provider": "fake", "model": "fake", **UsageTotals.from_events(event_log.list_events("source")).to_dict()}
    ]
    assert [row["bot"] for row in source["usage"]["by_bot"]] == [None]
    assert (
        fork["usage"]["inherited"]["requests"],
        fork["usage"]["requests"],
        fork["usage"]["running"]["requests"],
    ) == (
        1,
        1,
        2,
    )
    assert report["usage_totals"]["requests"] == 3


def test_report_lists_usage_limit_stops(event_log: SQLiteEventLog) -> None:
    _runner(event_log, limits=UsageLimits(max_requests=1)).run(GOAL, run_id="r")

    usage = build_run_report(event_log.list_events("r"))["runs"][0]["usage"]

    assert usage["limit_stops"] == [{"limit": "max_requests", "value": 1, "cap": 1, "phase": "before_call", "step": 3}]


def test_trace_exports_gen_ai_usage_cost_and_the_limit_stop(event_log: SQLiteEventLog) -> None:
    provider = FakeLLMAdapter(model="gpt-6.2-sol")
    _runner(event_log, provider=provider, limits=UsageLimits(max_requests=1)).run(GOAL, run_id="r")
    events = event_log.list_events("r")
    record = _of(event_log, "r", EventType.LLM_USAGE)[0].payload

    trace = build_trace(events)
    model_span = next(span for span in trace.spans if span.attributes.get("gen_ai.operation.name") == "chat")

    assert model_span.attributes["gen_ai.usage.input_tokens"] == record["usage"]["input_tokens"]
    assert model_span.attributes["gen_ai.usage.output_tokens"] == record["usage"]["output_tokens"]
    assert model_span.attributes["gen_ai.usage.cache_read.input_tokens"] == 0
    assert model_span.attributes["multi_bot_agentic.usage.cost_usd"] == record["cost"]["usd"]
    assert trace.root.attributes["multi_bot_agentic.usage.cost_usd"] == record["cost"]["usd"]
    assert trace.root.attributes["multi_bot_agentic.run.state"] == "usage_limit_exceeded"
    stop = next(event for event in trace.root.events if event.name == "multi_bot_agentic.usage_limit_exceeded")
    assert stop.attributes["multi_bot_agentic.usage_limit.name"] == "max_requests"

    diagram = render_mermaid(events).splitlines()
    usage = record["usage"]
    cost = record["cost"]["usd"]
    assert (
        f"    Note over A1: usage: {usage['input_tokens']} in / {usage['output_tokens']} out tokens, ${cost}" in diagram
    )
    assert "    Note over O: usage limit: the next model call would exceed max_requests=1 (requests=1)" in diagram
    assert diagram[-1] == "    Note over O: stopped: usage limit exceeded (resume with a higher limit)"


def test_eval_scenarios_assert_token_and_cost_budgets(tmp_path: Path) -> None:
    scripted = ("TOOL:checklist:ship", "DONE: shipped")
    scenarios = (
        EvalScenario("tight", GOAL, scripted, ("checklist",), expected_answer="shipped", max_total_tokens=10),
        EvalScenario("free", GOAL, scripted, ("checklist",), expected_answer="shipped", max_cost_usd=0),
        EvalScenario(
            "unpriced",
            GOAL,
            scripted,
            ("checklist",),
            expected_answer="shipped",
            max_cost_usd=1,
            model="gemini-3.8-flash",
        ),
    )

    report = EvaluationHarness(scenarios).run(root=tmp_path, event_log_dir=tmp_path / "logs")
    tight, free, unpriced = report.scenarios

    assert [item.passed for item in report.scenarios] == [False, True, False]
    assert tight.details["budget_checks"][0]["budget"] == "max_total_tokens"
    assert tight.details["budget_checks"][0]["value"] > 10
    assert free.details["budget_checks"] == [{"budget": "max_cost_usd", "value": 0.0, "cap": 0.0, "passed": True}]
    assert unpriced.details["budget_checks"][0]["value"] is None
    assert report.usage_totals.requests == 6


def test_eval_fixture_budgets_are_validated(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"scenario_id": "bad", "goal": GOAL, "max_total_tokens": 1.5}))

    with pytest.raises(ValueError, match="max_total_tokens must be an integer >= 0"):
        load_scenario(path)


def test_a_crash_while_recording_an_after_call_stop_never_lets_resume_finish_above_the_cap(
    event_log: SQLiteEventLog, monkeypatch: MonkeyPatch
) -> None:
    """The call that crossed the limit answered DONE; dying while stopping must not turn that into a success."""

    insert = SQLiteEventLog._insert

    def die_while_stopping(
        log: SQLiteEventLog, run_id: str, state: RunState, event_type: EventType, payload: dict[str, Any]
    ) -> EventRecord:
        if state is RunState.USAGE_LIMIT_EXCEEDED:
            raise _Crash
        return insert(log, run_id, state, event_type, payload)

    monkeypatch.setattr(SQLiteEventLog, "_insert", die_while_stopping)
    with pytest.raises(_Crash):
        _runner(event_log, limits=UsageLimits(max_total_tokens=150)).run(GOAL, run_id="r")
    monkeypatch.setattr(SQLiteEventLog, "_insert", insert)

    resumed = _runner(event_log).resume("r")

    assert resumed.state is RunState.USAGE_LIMIT_EXCEEDED
    assert resumed.usage is not None and resumed.usage.total_tokens is not None and resumed.usage.total_tokens > 150
    assert _of(event_log, "r", EventType.RUN_COMPLETED) == []


def test_a_limit_set_at_resume_survives_a_crash_before_the_next_checkpoint(event_log: SQLiteEventLog) -> None:
    """A resume that tightens the budget records it before it advances, like a grown approval policy."""

    with pytest.raises(_Crash):
        _runner(event_log, provider=CrashingProvider(crash_on=2)).run(GOAL, run_id="r")
    with pytest.raises(_Crash):
        _runner(event_log, limits=UsageLimits(max_total_tokens=100), provider=CrashingProvider(crash_on=1)).resume("r")

    resumed = _runner(event_log).resume("r")

    assert resumed.state is RunState.USAGE_LIMIT_EXCEEDED
    assert resumed.usage_limit is not None and (resumed.usage_limit.limit, resumed.usage_limit.cap) == (
        "max_total_tokens",
        100,
    )


CLAUDE_ERROR = {
    "type": "result",
    "subtype": "error_max_turns",
    "is_error": True,
    "result": "",
    "total_cost_usd": 0.02,
    "usage": {"input_tokens": 100, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0, "output_tokens": 20},
}


def _billed_failure(case: str, monkeypatch: MonkeyPatch) -> object:
    """Return a provider whose call fails after its provider reported usage (so it may be billed)."""

    if case.startswith("claude"):
        returncode = 1 if case == "claude-exit-1" else 0

        def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(command, returncode, stdout=json.dumps(CLAUDE_ERROR), stderr="")

        monkeypatch.setattr(subprocess, "run", fake_run)
        return ClaudeCodeCLIAdapter(command="claude -p --output-format json")
    usage = {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120}
    if case == "openai":
        response: dict[str, Any] = {"choices": [], "usage": usage}
    else:
        response = {
            "candidates": [{"finishReason": "MALFORMED_FUNCTION_CALL"}],
            "usageMetadata": {"promptTokenCount": 100, "candidatesTokenCount": 20, "totalTokenCount": 120},
        }

    def fake_post_json(*_args: object, **_kwargs: object) -> dict[str, Any]:
        return response

    monkeypatch.setattr(f"multi_bot_agentic.llm.{case}.post_json", fake_post_json)
    if case == "openai":
        return OpenAIAdapter(api_key="k", model="gpt-6.2-sol", base_url="https://example.test")
    return GeminiAdapter(api_key="k", model="gemini-4-neon")


@pytest.mark.parametrize("case", ["claude-error-result", "claude-exit-1", "openai", "gemini"])
def test_a_failed_call_that_reported_usage_is_still_recorded(
    event_log: SQLiteEventLog, monkeypatch: MonkeyPatch, case: str
) -> None:
    """The run fails as before, but the call its provider reported usage for stays in the totals."""

    result = _runner(event_log, provider=_billed_failure(case, monkeypatch)).run(GOAL, run_id="r")

    assert result.state is RunState.FAILED
    records = _of(event_log, "r", EventType.LLM_USAGE)
    assert len(records) == 1
    assert (records[0].payload["usage"]["input_tokens"], records[0].payload["usage"]["output_tokens"]) == (100, 20)
    assert result.usage is not None and result.usage.requests == 1
    if case.startswith("claude"):
        assert records[0].payload["cost"] == {"usd": 0.02, "source": "provider", "notes": ["reported by the provider"]}


def test_trace_names_the_model_claude_code_reported(event_log: SQLiteEventLog, monkeypatch: MonkeyPatch) -> None:
    result = {
        "type": "result",
        "is_error": False,
        "result": "DONE: shipped",
        "total_cost_usd": 0.01,
        "modelUsage": {"claude-opus-5-5": {"inputTokens": 10, "outputTokens": 5}},
    }

    def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps(result), stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    _runner(event_log, provider=ClaudeCodeCLIAdapter(command="claude -p --output-format json")).run(GOAL, run_id="r")

    trace = build_trace(event_log.list_events("r"))
    model_span = next(span for span in trace.spans if span.attributes.get("gen_ai.operation.name") == "chat")
    assert model_span.name == "chat claude-opus-5-5"
    assert model_span.attributes["gen_ai.request.model"] == "claude-opus-5-5"
    assert trace.root.attributes["gen_ai.request.model"] == "claude-opus-5-5"


def test_trace_and_mermaid_keep_a_provider_reported_cost_without_token_usage(event_log: SQLiteEventLog) -> None:
    _runner(event_log, provider=CostOnlyProvider()).run(GOAL, run_id="r")
    events = event_log.list_events("r")

    spans = [span for span in build_trace(events).spans if span.attributes.get("gen_ai.operation.name") == "chat"]
    assert [span.attributes.get("multi_bot_agentic.usage.cost_usd") for span in spans] == [0.25, 0.25]
    assert all("gen_ai.usage.input_tokens" not in span.attributes for span in spans)
    assert render_mermaid(events).count("    Note over A1: usage: tokens not reported, $0.25") == 2


@pytest.mark.parametrize(
    ("usage", "limits", "stopped_by"),
    [
        (Usage(input_tokens=7), UsageLimits(max_input_tokens=100), None),
        (Usage(input_tokens=7), UsageLimits(max_output_tokens=100), "max_output_tokens"),
        (Usage(total_tokens=9), UsageLimits(max_total_tokens=100), None),
        (Usage(total_tokens=9), UsageLimits(max_input_tokens=100), "max_input_tokens"),
    ],
)
def test_a_limit_is_unmeasurable_only_when_its_own_counter_is_unreported(
    event_log: SQLiteEventLog, usage: Usage, limits: UsageLimits, stopped_by: str | None
) -> None:
    result = _runner(event_log, limits=limits, provider=PartialUsageProvider(usage)).run(GOAL, run_id="r")

    if stopped_by is None:
        assert result.state is RunState.SUCCEEDED
    else:
        assert result.state is RunState.USAGE_LIMIT_EXCEEDED
        assert result.usage_limit is not None
        assert (result.usage_limit.limit, result.usage_limit.value) == (stopped_by, None)
