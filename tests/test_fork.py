"""Tests for time-travel forks: rebuilding a run's state after step N and branching from it."""

from __future__ import annotations

import base64
import itertools
import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest

from multi_bot_agentic import models
from multi_bot_agentic.bots import BotSpec
from multi_bot_agentic.checkpoint import load_latest_checkpoint, snapshot_from_event
from multi_bot_agentic.event_log import EventRecord, SQLiteEventLog
from multi_bot_agentic.fork import (
    ForkError,
    build_history,
    event_digest,
    inherited_events_intact,
    plan_fork,
    prefix_digest,
    reconstruct_fork_point,
    run_lineage,
)
from multi_bot_agentic.llm.fake import FakeLLMAdapter
from multi_bot_agentic.models import EventType, ModelOutput, ModelRequest
from multi_bot_agentic.runner import AgentRunner, build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tracing import build_trace, render_mermaid, render_otlp_json
from multi_bot_agentic.tracing.spans import span_id_for, trace_id_for

GOAL = "Create a launch checklist"
NEW_GOAL = "Create a rollback checklist"
TOOLS = frozenset({"checklist", "echo"})
UUID_PATTERN = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


class _CrashError(BaseException):
    """Stands in for the process dying mid-step: the runner cannot record a terminal event."""


class _ScriptedProvider:
    """Provider that replays scripted replies (or raises scripted errors)."""

    provider_name = "fake"

    def __init__(self, *script: str | BaseException) -> None:
        self.script = list(script)

    def complete(self, request: ModelRequest, timeout_seconds: float) -> ModelOutput:
        del request, timeout_seconds
        item = self.script.pop(0) if self.script else "DONE: unscripted"
        if isinstance(item, BaseException):
            raise item
        return ModelOutput(provider=self.provider_name, text=item, raw={})


def _bots() -> dict[str, BotSpec]:
    return {
        "planner": BotSpec(bot_id="planner", name="Planner", allowed_tools=frozenset({"checklist"})),
        "writer": BotSpec(bot_id="writer", name="Writer", allowed_tools=frozenset({"echo"})),
    }


def _runner(
    log: SQLiteEventLog,
    root: Path,
    provider: Any,
    *,
    max_steps: int = 6,
    bots: dict[str, BotSpec] | None = None,
    active_bot_id: str | None = None,
) -> AgentRunner:
    return AgentRunner(
        provider=provider,
        event_log=log,
        tools=build_default_tools(root=root),
        safety_policy=SafetyPolicy(max_steps=max_steps, allowed_tools=TOOLS),
        bots=bots,
        active_bot_id=active_bot_id,
    )


@pytest.fixture
def log(tmp_path: Path) -> Iterator[SQLiteEventLog]:
    event_log = SQLiteEventLog(tmp_path / "runs.sqlite")
    yield event_log
    event_log.close()


def _fake_run(log: SQLiteEventLog, root: Path, run_id: str = "demo") -> list[EventRecord]:
    """Record the fake provider's 4-step run: model -> checklist tool -> model -> finish."""

    result = _runner(log, root, FakeLLMAdapter()).run(GOAL, run_id=run_id)
    assert (result.state.value, result.steps) == ("succeeded", 4)
    return log.list_events(run_id)


def _checkpoint(events: list[EventRecord], step: int) -> EventRecord:
    return next(event for event in events if event.event_type == "checkpoint" and event.payload["step"] == step)


def _own_events(events: list[EventRecord]) -> list[EventRecord]:
    """Return a fork's events after its inherited copies."""

    lineage = run_lineage(events)
    assert lineage is not None
    return [event for event in events if event.seq > lineage.seq + lineage.inherited_events]


def _normalized(events: list[EventRecord]) -> list[tuple[str, str, Any]]:
    """Return (type, state, payload) with observation ids renamed in order of first appearance."""

    aliases: dict[str, str] = {}
    normalized = []
    for event in events:
        text = json.dumps(event.payload, sort_keys=True)
        for found in UUID_PATTERN.findall(text):
            aliases.setdefault(found, f"id-{len(aliases)}")
        for raw, alias in aliases.items():
            text = text.replace(raw, alias)
        normalized.append((event.event_type, event.state, json.loads(text)))
    return normalized


def test_fork_point_is_the_checkpoint_written_after_that_step(log: SQLiteEventLog, tmp_path: Path) -> None:
    """The state after step N is exactly what the checkpoint of step N holds; step 0 is the goal."""

    events = _fake_run(log, tmp_path)

    for step in (1, 2, 3):
        point = reconstruct_fork_point(events, step)
        checkpoint = _checkpoint(events, step)
        snapshot = snapshot_from_event(checkpoint)
        assert (point.goal, point.observations, point.bot) == (snapshot.goal, snapshot.observations, None)
        assert point.event == checkpoint
        assert point.prefix == tuple(event for event in events if event.seq <= checkpoint.seq)
    start = reconstruct_fork_point(events, 0)
    first_observation = next(event for event in events if event.event_type == "observation")
    assert [item.to_dict() for item in start.observations] == [first_observation.payload]
    assert [event.event_type for event in start.prefix] == ["run_created"]


def test_fork_continues_exactly_like_resume_after_a_crash_at_that_step(log: SQLiteEventLog, tmp_path: Path) -> None:
    """Forking a finished run after step 2 does what ``resume`` does when the run died right after step 2."""

    _runner(log, tmp_path, _ScriptedProvider("TOOL:checklist:ship it", "DONE: shipped")).run(GOAL, run_id="done")
    with pytest.raises(_CrashError):
        _runner(log, tmp_path, _ScriptedProvider("TOOL:checklist:ship it", _CrashError())).run(GOAL, run_id="crashed")
    restored = load_latest_checkpoint(log, "crashed")
    before_resume = len(log.list_events("crashed"))
    resumed = _runner(log, tmp_path, _ScriptedProvider("DONE: shipped")).resume("crashed")
    point = reconstruct_fork_point(log.list_events("done"), 2)
    forked = _runner(log, tmp_path, _ScriptedProvider("DONE: shipped")).fork("done", 2, "branch")
    own = _own_events(log.list_events("branch"))
    loop = next(index for index, event in enumerate(own) if event.event_type == "state_transition")

    assert restored is not None and restored.step == 2
    assert [(item.source, item.content) for item in point.observations] == [
        (item.source, item.content) for item in restored.observations
    ]
    assert (forked.state, forked.answer, forked.steps) == (resumed.state, resumed.answer, resumed.steps)
    assert _normalized(own[loop:]) == _normalized(log.list_events("crashed")[before_resume:])


def test_fork_writes_lineage_then_inherited_copies_and_leaves_the_source_untouched(
    log: SQLiteEventLog, tmp_path: Path
) -> None:
    """The fork starts with run_forked, copies the source up to the fork point, then checkpoints its start."""

    source = _fake_run(log, tmp_path)
    result = _runner(log, tmp_path, FakeLLMAdapter()).fork("demo", 1, "rollback", goal=NEW_GOAL)
    fork = log.list_events("rollback")
    checkpoint = _checkpoint(source, 1)
    inherited = [event for event in source if event.seq <= checkpoint.seq]
    copies = fork[1 : len(inherited) + 1]
    start = fork[len(inherited) + 1]

    assert log.list_events("demo") == source
    assert result.state.value == "succeeded"
    assert fork[0].event_type == EventType.RUN_FORKED.value
    assert fork[0].payload == {
        "parent_run_id": "demo",
        "fork_step": 1,
        "parent_event": {"seq": checkpoint.seq, "event_type": "checkpoint", "sha256": event_digest(checkpoint)},
        "inherited_events": len(inherited),
        "prefix_sha256": prefix_digest(inherited),
        "goal": NEW_GOAL,
        "provider": "fake",
        "bot": None,
        "max_steps": 6,
        "overrides": {"goal": NEW_GOAL},
    }
    assert [(e.event_type, e.state, e.payload) for e in copies] == [
        (e.event_type, e.state, e.payload) for e in inherited
    ]
    assert [event.seq for event in copies] == [event.seq + 1 for event in inherited]
    lineage = run_lineage(fork)
    assert lineage is not None and inherited_events_intact(fork, lineage)
    assert (start.event_type, start.payload["step"], start.payload["goal"]) == ("checkpoint", 1, NEW_GOAL)
    assert start.payload["observations"][-1]["content"] == NEW_GOAL
    assert reconstruct_fork_point(fork, 1).goal == NEW_GOAL
    assert reconstruct_fork_point(fork, 0).goal == GOAL


def test_a_new_goal_is_answered_before_the_stale_tool_request(log: SQLiteEventLog, tmp_path: Path) -> None:
    """After step 1 the model had asked for checklist with the old goal; the fork asks the model first."""

    _fake_run(log, tmp_path)
    _runner(log, tmp_path, FakeLLMAdapter()).fork("demo", 1, "rollback", goal=NEW_GOAL)
    own = _own_events(log.list_events("rollback"))
    decisions = [event.payload for event in own if event.event_type == "decision"]
    requests = [event.payload for event in own if event.event_type == "action_requested"]

    assert (decisions[0]["action"], decisions[0]["rationale"]["rule_id"]) == ("call_llm", "observe.new-user-goal")
    assert [request["payload"] for request in requests if request["action"] == "call_tool"] == [{"text": NEW_GOAL}]


@pytest.mark.parametrize("at_step", [0, 1])
def test_a_fork_that_dies_in_its_first_step_resumes_with_its_overrides(
    log: SQLiteEventLog, tmp_path: Path, at_step: int
) -> None:
    """The fork checkpoints its starting state, so ``resume`` keeps the new goal; tracing counts the resume."""

    _fake_run(log, tmp_path)
    with pytest.raises(_CrashError):
        _runner(log, tmp_path, _ScriptedProvider(_CrashError())).fork("demo", at_step, "branch", goal=NEW_GOAL)
    resumed = _runner(log, tmp_path, FakeLLMAdapter()).resume("branch")
    requests = [event.payload for event in log.list_events("branch") if event.event_type == "action_requested"]
    root = build_trace(log.list_events("branch")).root

    assert resumed.state.value == "succeeded"
    assert [request["payload"] for request in requests if request["action"] == "call_tool"][-1] == {"text": NEW_GOAL}
    assert root.attributes["multi_bot_agentic.run.resume_count"] == 1


def test_forks_with_the_fake_provider_are_deterministic_including_a_fork_of_a_fork(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Running the same forks twice writes identical events, lineage digests included."""

    def scenario(path: Path) -> dict[str, list[tuple[str, str, Any]]]:
        counter = itertools.count(1)
        monkeypatch.setattr(models, "uuid4", lambda: UUID(int=next(counter)))
        event_log = SQLiteEventLog(path)
        try:
            _fake_run(event_log, tmp_path)
            _runner(event_log, tmp_path, FakeLLMAdapter()).fork("demo", 1, "rollback", goal=NEW_GOAL)
            writer = _runner(event_log, tmp_path, FakeLLMAdapter(tool_name="echo"), bots=_bots())
            assert writer.fork("rollback", 2, "rollback-notes", bot_id="writer").state.value == "succeeded"
            return {
                run_id: [(event.event_type, event.state, event.payload) for event in event_log.list_events(run_id)]
                for run_id in ("demo", "rollback", "rollback-notes")
            }
        finally:
            event_log.close()

    first = scenario(tmp_path / "first.sqlite")
    second = scenario(tmp_path / "second.sqlite")
    grandchild = first["rollback-notes"]
    tools = [payload["tool"] for kind, _, payload in grandchild if kind == "action_result" and "tool" in payload]

    assert first == second
    assert grandchild[0][2]["parent_run_id"] == "rollback"
    assert (grandchild[1][0], grandchild[1][2]["parent_run_id"]) == ("run_forked", "demo")
    assert tools == ["echo"]


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"at_step": 4}, r"step 4 ended run demo \(finish -> succeeded\); forkable steps: 0, 1, 2, 3$"),
        ({"at_step": 9}, r"step 9 is beyond the last step of run demo \(step 4\)"),
        ({"new_run_id": "demo"}, r"run demo already exists"),
        ({"new_run_id": "taken"}, r"run taken already exists"),
        ({"source_run_id": "missing"}, r"run missing not found"),
        ({"bot_id": "admin"}, r"bot admin is not registered \(registered bots: ops, planner, writer\)"),
        ({"bot_id": "ops"}, r"bot ops allows tools outside the safety policy allowlist \(readonly_file\)"),
        ({"max_steps": 2}, r"max_steps=2 leaves no step after step 2"),
        ({"goal": "   "}, r"goal rejected: goal must be non-empty"),
    ],
)
def test_invalid_forks_are_rejected_before_anything_is_written(
    log: SQLiteEventLog, tmp_path: Path, change: dict[str, Any], message: str
) -> None:
    """Bad steps, taken ids, unknown or over-privileged bots, budgets, and goals all fail closed."""

    _fake_run(log, tmp_path)
    _fake_run(log, tmp_path, run_id="taken")
    ops = BotSpec(bot_id="ops", name="Ops", allowed_tools=frozenset({"checklist", "readonly_file"}))
    request: dict[str, Any] = {"source_run_id": "demo", "at_step": 2, "new_run_id": "branch", "max_steps": 6} | change
    runner = _runner(log, tmp_path, FakeLLMAdapter(), bots=_bots() | {"ops": ops}, max_steps=request.pop("max_steps"))
    before = log.list_events()

    with pytest.raises(ForkError, match=message):
        runner.fork(request.pop("source_run_id"), request.pop("at_step"), request.pop("new_run_id"), **request)
    assert log.list_events() == before


def test_an_interrupted_run_forks_before_the_step_it_died_in(log: SQLiteEventLog, tmp_path: Path) -> None:
    """The step a run died in has no result; earlier steps fork, and the source stays resumable."""

    with pytest.raises(_CrashError):
        _runner(log, tmp_path, _ScriptedProvider("TOOL:checklist:ship it", _CrashError())).run(GOAL, run_id="crashed")
    history = build_history(log.list_events("crashed"))
    before = log.list_events("crashed")

    assert (history.final_state, history.forkable_steps(), history.steps[-1].outcome) == (
        "unfinished",
        (0, 1, 2),
        "interrupted",
    )
    with pytest.raises(ForkError, match=r"step 3 of run crashed never recorded a result"):
        _runner(log, tmp_path, FakeLLMAdapter()).fork("crashed", 3, "branch")
    result = _runner(log, tmp_path, _ScriptedProvider("DONE: recovered")).fork("crashed", 2, "branch")
    assert (result.state.value, result.answer) == ("succeeded", "recovered")
    assert log.list_events("crashed") == before


def test_the_bot_of_the_fork_point_comes_from_the_registry(log: SQLiteEventLog, tmp_path: Path) -> None:
    """A fork restores the checkpoint's bot only when this runner registers it, with the registered scope."""

    planner = _runner(log, tmp_path, FakeLLMAdapter(), bots=_bots(), active_bot_id="planner")
    assert planner.run(GOAL, run_id="crew").state.value == "succeeded"

    with pytest.raises(ForkError, match=r"step 1 of run crew ran as bot planner, which is not registered"):
        _runner(log, tmp_path, FakeLLMAdapter()).fork("crew", 1, "branch")
    plan = plan_fork(log, "crew", 1, "branch", provider="fake", policy=SafetyPolicy(allowed_tools=TOOLS), bots=_bots())
    assert (plan.bot, plan.allowed_tools, plan.next_decision.target) == (
        "planner",
        frozenset({"checklist"}),
        "checklist",
    )


def test_switching_bots_hands_off_before_a_pending_tool_request_can_run(log: SQLiteEventLog, tmp_path: Path) -> None:
    """No escalation through ``bot_id``: a tool request the old bot could not run never runs under the new bot.

    The writer (echo only) asked for checklist, which the engine refused. Forking that state as the
    planner (checklist allowed) must not execute the stale request: the switch is a handoff, so the
    planner's first step is a model call under its own scope.
    """

    writer = _runner(
        log, tmp_path, _ScriptedProvider("TOOL:checklist:read the secrets"), bots=_bots(), active_bot_id="writer"
    )
    assert writer.run(GOAL, run_id="writer-run").answer == "unscripted"
    assert build_history(log.list_events("writer-run")).steps[2].rule_id == "model.disallowed-tool-request"
    planner = _runner(log, tmp_path, _ScriptedProvider("DONE: planned without the tool"), bots=_bots())
    plan = plan_fork(
        log,
        "writer-run",
        1,
        "as-planner",
        provider="fake",
        policy=planner.safety_policy,
        bots=_bots(),
        bot_id="planner",
    )
    result = planner.fork("writer-run", 1, "as-planner", bot_id="planner")
    own = _own_events(log.list_events("as-planner"))

    assert plan.observations[1].content == "TOOL:checklist:read the secrets"
    assert (plan.next_decision.action, plan.next_decision.rationale.rule_id) == (
        "call_llm",
        "handoff.needs-continuation",
    )
    assert (result.state.value, result.answer) == ("succeeded", "planned without the tool")
    assert [event.payload["action"] for event in own if event.event_type == "action_requested"] == ["call_llm"]
    assert own[0].payload == {
        "kind": "handoff",
        "fork_override": True,
        "from_bot": "writer",
        "to_bot": "planner",
        "summary": "forked from writer-run after step 1",
        "allowed_tools": ["checklist"],
    }


def test_the_fork_budget_counts_inherited_steps(log: SQLiteEventLog, tmp_path: Path) -> None:
    """``max_steps`` is the whole budget: forking after step 2 with max_steps=3 leaves one final step."""

    _fake_run(log, tmp_path)
    plan = plan_fork(log, "demo", 2, "short", provider="fake", policy=SafetyPolicy(max_steps=3, allowed_tools=TOOLS))
    result = _runner(log, tmp_path, FakeLLMAdapter(), max_steps=3).fork("demo", 2, "short")
    last_decision = [event for event in log.list_events("short") if event.event_type == "decision"][-1]

    assert plan.remaining_steps == 1
    assert (result.state.value, result.steps) == ("succeeded", 3)
    assert last_decision.payload["rationale"]["rule_id"] == "model.done-or-budget"


def test_history_lists_bots_rules_outcomes_and_inherited_steps(log: SQLiteEventLog, tmp_path: Path) -> None:
    """``history`` rows carry the bot, action, rule, outcome, and whether the step can be forked."""

    _fake_run(log, tmp_path)
    _runner(log, tmp_path, FakeLLMAdapter(tool_name="echo"), bots=_bots()).fork("demo", 1, "notes", bot_id="writer")
    history = build_history(log.list_events("notes"))
    rows = [
        (row.step, row.bot, row.action, row.rule_id, row.outcome, row.forkable, row.inherited) for row in history.steps
    ]

    assert rows == [
        (0, None, None, None, "start", True, True),
        (1, None, "call_llm", "observe.no-model-output", "TOOL", True, True),
        (2, "writer", "call_llm", "handoff.needs-continuation", "TOOL echo", True, False),
        (3, "writer", "call_tool", "model.requested-tool", "echo ok", True, False),
        (4, "writer", "call_llm", "tool.result-needs-synthesis", "DONE", True, False),
        (5, "writer", "finish", "model.done-or-budget", "succeeded", False, False),
    ]
    assert history.lineage is not None
    assert (history.lineage.parent_run_id, history.lineage.fork_step, dict(history.lineage.overrides)) == (
        "demo",
        1,
        {"bot": "writer"},
    )


def test_history_names_only_directive_targets_the_run_used(log: SQLiteEventLog, tmp_path: Path) -> None:
    """A directive target is model output: ``history`` names it only for a tool the run called or a bot it ran."""

    leaky = "TOOL:mail ops@example.com the key sk-FAKEhistory0123456789:now"
    _runner(log, tmp_path, _ScriptedProvider(leaky, "TOOL:checklist:ship it", "DONE: shipped")).run(
        GOAL, run_id="leaky"
    )
    history = build_history(log.list_events("leaky"))

    assert [row.outcome for row in history.steps] == [
        "start",
        "TOOL",
        "TOOL checklist",
        "checklist ok",
        "DONE",
        "succeeded",
    ]
    assert "example.com" not in json.dumps(history.to_dict())


def test_fork_trace_links_to_the_parent_root_span_and_marks_inherited_spans(
    log: SQLiteEventLog, tmp_path: Path
) -> None:
    """The fork's root span links to the parent's root span, and its own start is not a resume."""

    _fake_run(log, tmp_path)
    _runner(log, tmp_path, FakeLLMAdapter()).fork("demo", 1, "rollback", goal=NEW_GOAL)
    trace = build_trace(log.list_events("rollback"))
    root = trace.root
    exported = json.loads(render_otlp_json(trace))["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
    chats = [span for span in trace.spans if span.name == "chat"]
    mermaid = render_mermaid(log.list_events("rollback"))

    assert exported["links"] == [
        {
            "traceId": trace_id_for("demo"),
            "spanId": span_id_for("demo", "root"),
            "attributes": [
                {"key": "multi_bot_agentic.link.type", "value": {"stringValue": "forked_from"}},
                {"key": "multi_bot_agentic.fork.step", "value": {"intValue": "1"}},
            ],
        }
    ]
    assert (
        root.attributes["multi_bot_agentic.fork.parent_run_id"],
        root.attributes["multi_bot_agentic.fork.step"],
    ) == (
        "demo",
        1,
    )
    assert root.attributes["multi_bot_agentic.fork.overrides"] == ["goal"]
    assert "multi_bot_agentic.run.resume_count" not in root.attributes
    assert [event.name for event in root.events].count("multi_bot_agentic.run.forked") == 1
    assert [span.attributes.get("multi_bot_agentic.fork.inherited", False) for span in chats] == [True, False, False]
    assert "Note over O: forked from demo after step 1 (new goal)" in mermaid
    assert mermaid.index("observe.no-model-output") < mermaid.index("forked from demo") < mermaid.index("new-user-goal")


def test_fork_link_parses_with_opentelemetry_proto(log: SQLiteEventLog, tmp_path: Path) -> None:
    """When opentelemetry-proto is installed, the fork's link parses into ``Span.Link``."""

    trace_service_pb2 = pytest.importorskip("opentelemetry.proto.collector.trace.v1.trace_service_pb2")
    json_format = pytest.importorskip("google.protobuf.json_format")
    _fake_run(log, tmp_path)
    _runner(log, tmp_path, FakeLLMAdapter()).fork("demo", 1, "rollback", goal=NEW_GOAL)
    payload = json.loads(render_otlp_json(build_trace(log.list_events("rollback"))))
    # OTLP/JSON hex-encodes ids; the generic protobuf JSON parser expects base64 bytes.
    for span in payload["resourceSpans"][0]["scopeSpans"][0]["spans"]:
        for item in (span, *span.get("links", [])):
            for key in ("traceId", "spanId", "parentSpanId"):
                if key in item:
                    item[key] = base64.b64encode(bytes.fromhex(item[key])).decode()
    request = json_format.ParseDict(payload, trace_service_pb2.ExportTraceServiceRequest())

    (link,) = request.resource_spans[0].scope_spans[0].spans[0].links
    assert (link.trace_id, link.span_id) == (
        bytes.fromhex(trace_id_for("demo")),
        bytes.fromhex(span_id_for("demo", "root")),
    )
