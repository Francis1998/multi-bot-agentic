"""Tests for typed multi-bot handoff parsing and isolation."""

from __future__ import annotations

from pathlib import Path

import pytest

from multi_bot_agentic.bots import BotSpec
from multi_bot_agentic.decision import DeterministicDecisionEngine
from multi_bot_agentic.event_log import EventRecord, SQLiteEventLog
from multi_bot_agentic.models import ModelOutput, ModelRequest, Observation, RunState
from multi_bot_agentic.runner import AgentRunner, build_default_tools
from multi_bot_agentic.safety import SafetyPolicy


def _bots() -> dict[str, BotSpec]:
    return {
        "planner": BotSpec(
            bot_id="planner",
            name="Planner",
            allowed_tools=frozenset({"checklist"}),
            description="Plans work",
        ),
        "writer": BotSpec(
            bot_id="writer",
            name="Writer",
            allowed_tools=frozenset({"echo"}),
            description="Writes final answers",
        ),
    }


def test_parse_handoff_to_registered_bot() -> None:
    """HANDOFF:bot_id:summary selects a registered bot."""

    engine = DeterministicDecisionEngine(provider_name="fake", bots=_bots())
    decision = engine.decide(
        (
            Observation(source="user", content="coordinate the crew"),
            Observation(source="llm:fake", content="HANDOFF:writer:please draft the answer"),
        ),
        step=1,
        policy=SafetyPolicy(max_steps=5, allowed_tools=frozenset({"checklist", "echo"})),
    )
    assert decision.action == "handoff"
    assert decision.target == "writer"
    assert decision.payload["summary"] == "please draft the answer"
    assert decision.rationale.rule_id == "model.requested-handoff"


def test_reject_unknown_handoff_bot() -> None:
    """Unknown handoff targets are rejected."""

    engine = DeterministicDecisionEngine(provider_name="fake", bots=_bots())
    decision = engine.decide(
        (
            Observation(source="user", content="coordinate the crew"),
            Observation(source="llm:fake", content="HANDOFF:shadow:steal tools"),
        ),
        step=1,
        policy=SafetyPolicy(max_steps=5, allowed_tools=frozenset({"checklist", "echo"})),
    )
    assert decision.action == "fail"
    assert "unknown bot" in str(decision.payload.get("reason", ""))


def test_runner_handoff_switches_allowlist_and_isolates_tools(tmp_path: Path) -> None:
    """Runner switches active bot tool scope and blocks prior-bot tools."""

    class ScriptedProvider:
        provider_name = "fake"

        def __init__(self) -> None:
            self.calls = 0

        def complete(self, request: ModelRequest, timeout_seconds: float) -> ModelOutput:
            del timeout_seconds
            self.calls += 1
            if self.calls == 1:
                return ModelOutput(provider=self.provider_name, text="HANDOFF:writer:draft now", raw={})
            if any(item.source.startswith("handoff:") for item in request.observations):
                return ModelOutput(
                    provider=self.provider_name,
                    text="DONE: drafted after handoff",
                    raw={"mode": "post-handoff"},
                )
            return ModelOutput(provider=self.provider_name, text="DONE: unexpected", raw={})

    log = SQLiteEventLog(tmp_path / "runs.sqlite")
    try:
        runner = AgentRunner(
            provider=ScriptedProvider(),
            event_log=log,
            tools=build_default_tools(root=tmp_path),
            safety_policy=SafetyPolicy(max_steps=6, allowed_tools=frozenset({"checklist", "echo"})),
            bots=_bots(),
            active_bot_id="planner",
        )
        assert runner.safety_policy.allowed_tools == frozenset({"checklist"})
        result = runner.run("Coordinate planner then writer", run_id="handoff-run")
    finally:
        log.close()

    assert result.state == RunState.SUCCEEDED
    assert result.answer == "drafted after handoff"
    assert runner.active_bot_id == "writer"
    assert runner.safety_policy.allowed_tools == frozenset({"echo"})

    engine = DeterministicDecisionEngine(provider_name="fake", bots=_bots())
    blocked = engine.decide(
        (
            Observation(source="user", content="goal"),
            Observation(source="llm:fake", content="TOOL:checklist:should fail"),
        ),
        step=1,
        policy=runner.safety_policy,
    )
    assert blocked.action == "call_llm"
    assert "not allowlisted" in str(blocked.payload.get("reason", ""))


def test_botspec_rejects_empty_allowlist() -> None:
    """BotSpec requires a non-empty tool allowlist."""

    with pytest.raises(ValueError, match="allowed_tools"):
        BotSpec(bot_id="x", name="X", allowed_tools=frozenset())


class _SimulatedCrash(BaseException):
    """Stands in for the process dying mid-step; the runner cannot record a terminal event."""


class _ScriptedProvider:
    """Provider that replays scripted outputs and raises scripted errors."""

    provider_name = "fake"

    def __init__(self, *script: str | BaseException) -> None:
        self.script = list(script)

    def complete(self, request: ModelRequest, timeout_seconds: float) -> ModelOutput:
        del request, timeout_seconds
        item = self.script.pop(0)
        if isinstance(item, BaseException):
            raise item
        return ModelOutput(provider=self.provider_name, text=item, raw={})


def _interrupted_handoff_run(log: SQLiteEventLog, tmp_path: Path, run_id: str) -> None:
    """Hand off planner -> writer, then crash (as if the process was killed) before finishing.

    A crash leaves no terminal event, so the run stays resumable. A handled failure such
    as a provider outage records ``run_failed``, which is final.
    """

    runner = AgentRunner(
        provider=_ScriptedProvider("HANDOFF:writer:draft now", _SimulatedCrash()),
        event_log=log,
        tools=build_default_tools(root=tmp_path),
        safety_policy=SafetyPolicy(max_steps=6, allowed_tools=frozenset({"checklist", "echo"})),
        bots=_bots(),
        active_bot_id="planner",
    )
    with pytest.raises(_SimulatedCrash):
        runner.run("Coordinate planner then writer", run_id=run_id)
    assert runner.active_bot_id == "writer"


def _resume_runner(log: SQLiteEventLog, tmp_path: Path, provider: _ScriptedProvider) -> AgentRunner:
    """Build a fresh runner exactly like the one that started the run."""

    return AgentRunner(
        provider=provider,
        event_log=log,
        tools=build_default_tools(root=tmp_path),
        safety_policy=SafetyPolicy(max_steps=6, allowed_tools=frozenset({"checklist", "echo"})),
        bots=_bots(),
        active_bot_id="planner",
    )


def test_resume_restores_active_bot_scope_from_checkpoint(tmp_path: Path) -> None:
    """A resumed run keeps the tool scope of the bot that was active at checkpoint time.

    Previously ``resume`` restarted with the constructor's ``active_bot_id``, so a run
    that had handed off to ``writer`` (``echo`` only) could execute the planner-only
    ``checklist`` tool after a crash/resume.
    """

    log = SQLiteEventLog(tmp_path / "runs.sqlite")
    try:
        _interrupted_handoff_run(log, tmp_path, "resume-scope")
        runner = _resume_runner(log, tmp_path, _ScriptedProvider("TOOL:checklist:escalate", "DONE: stayed scoped"))
        result = runner.resume("resume-scope")
        events = log.list_events("resume-scope")
    finally:
        log.close()

    executed_tools = [
        event.payload.get("tool")
        for event in events
        if event.event_type == "action_result" and event.payload.get("kind") == "tool"
    ]
    assert executed_tools == []
    assert result.state == RunState.SUCCEEDED
    assert result.answer == "stayed scoped"
    assert runner.active_bot_id == "writer"
    assert runner.safety_policy.allowed_tools == frozenset({"echo"})
    rejected = [
        event.payload["payload"]["reason"]
        for event in events
        if event.event_type == "decision" and event.payload["rationale"]["rule_id"] == "model.disallowed-tool-request"
    ]
    assert rejected == ["requested tool is not allowlisted: checklist"]


def test_resume_executes_handoff_decisions(tmp_path: Path) -> None:
    """A handoff requested after resume is executed instead of failing the run."""

    log = SQLiteEventLog(tmp_path / "runs.sqlite")
    try:
        _interrupted_handoff_run(log, tmp_path, "resume-handoff")
        runner = _resume_runner(log, tmp_path, _ScriptedProvider("HANDOFF:planner:back to you", "DONE: handed back"))
        result = runner.resume("resume-handoff")
        events = log.list_events("resume-handoff")
    finally:
        log.close()

    assert result.state == RunState.SUCCEEDED
    assert result.answer == "handed back"
    assert runner.active_bot_id == "planner"
    handoffs = [
        (event.payload["from_bot"], event.payload["to_bot"])
        for event in events
        if event.event_type == "action_result" and event.payload.get("kind") == "handoff"
    ]
    assert handoffs == [("planner", "writer"), ("writer", "planner")]


def test_resume_rejects_checkpoint_bot_missing_from_registry(tmp_path: Path) -> None:
    """Resuming a bot-scoped checkpoint without that bot registered fails closed."""

    log = SQLiteEventLog(tmp_path / "runs.sqlite")
    try:
        _interrupted_handoff_run(log, tmp_path, "resume-missing-bot")
        runner = AgentRunner(
            provider=_ScriptedProvider("DONE: should not run"),
            event_log=log,
            tools=build_default_tools(root=tmp_path),
            safety_policy=SafetyPolicy(max_steps=6, allowed_tools=frozenset({"checklist", "echo"})),
        )
        with pytest.raises(ValueError, match="checkpoint active bot is not registered: writer"):
            runner.resume("resume-missing-bot")
    finally:
        log.close()


def _executed_tools(events: list[EventRecord]) -> list[object]:
    """Return the tools a run actually executed, in order."""

    return [
        event.payload.get("tool")
        for event in events
        if event.event_type == "action_result" and event.payload.get("kind") == "tool"
    ]


@pytest.mark.parametrize("previous_call", ["run", "resume"])
def test_each_run_starts_with_the_constructor_bot_scope(tmp_path: Path, previous_call: str) -> None:
    """A handoff lasts only for its own run, so reusing a runner must not leak a bot's tools.

    ``run`` used to start from the bot that the runner's previous ``run`` handed off to (or
    that its previous ``resume`` restored). The next, unrelated run could then call that
    bot's tools, here the writer-only ``echo``, although it should start as ``planner`` and
    its own event log has no handoff that would allow it.
    """

    log = SQLiteEventLog(tmp_path / "runs.sqlite")
    try:
        if previous_call == "run":
            provider = _ScriptedProvider("HANDOFF:writer:draft now", "DONE: drafted", "TOOL:echo:leak", "DONE: planned")
            runner = _resume_runner(log, tmp_path, provider)
            runner.run("Coordinate planner then writer", run_id="earlier")
        else:
            _interrupted_handoff_run(log, tmp_path, "earlier")
            provider = _ScriptedProvider("DONE: drafted", "TOOL:echo:leak", "DONE: planned")
            runner = _resume_runner(log, tmp_path, provider)
            runner.resume("earlier")
        assert runner.active_bot_id == "writer"
        result = runner.run("Plan the next release", run_id="next")
        events = log.list_events("next")
    finally:
        log.close()

    assert (result.state, result.answer) == (RunState.SUCCEEDED, "planned")
    assert _executed_tools(events) == []
    checkpoint_bots = {event.payload.get("active_bot_id") for event in events if event.event_type == "checkpoint"}
    assert checkpoint_bots == {"planner"}
    rejected = [
        event.payload["payload"]["reason"]
        for event in events
        if event.event_type == "decision" and event.payload["rationale"]["rule_id"] == "model.disallowed-tool-request"
    ]
    assert rejected == ["requested tool is not allowlisted: echo"]


def test_resume_starts_from_the_constructor_scope_not_an_earlier_handoff(tmp_path: Path) -> None:
    """A checkpoint without a bot resumes with the constructor's scope, as on a fresh runner.

    This runner keeps no bot active, so the interrupted run may use every policy tool. A
    handoff to ``writer`` made by an earlier run on the same runner used to stay in force,
    and the resumed run lost ``checklist`` although its own log never handed off.
    """

    def unscoped_runner(provider: _ScriptedProvider) -> AgentRunner:
        return AgentRunner(
            provider=provider,
            event_log=log,
            tools=build_default_tools(root=tmp_path),
            safety_policy=SafetyPolicy(max_steps=6, allowed_tools=frozenset({"checklist", "echo"})),
            bots=_bots(),
        )

    log = SQLiteEventLog(tmp_path / "runs.sqlite")
    try:
        with pytest.raises(_SimulatedCrash):
            unscoped_runner(_ScriptedProvider("Planning first", _SimulatedCrash())).run("Ship it", run_id="interrupted")
        runner = unscoped_runner(
            _ScriptedProvider("HANDOFF:writer:draft now", "DONE: drafted", "TOOL:checklist:ship it", "DONE: shipped")
        )
        runner.run("Hand the draft to the writer", run_id="earlier")
        assert runner.active_bot_id == "writer"
        result = runner.resume("interrupted")
        events = log.list_events("interrupted")
    finally:
        log.close()

    assert (result.state, result.answer) == (RunState.SUCCEEDED, "shipped")
    assert _executed_tools(events) == ["checklist"]
    assert runner.active_bot_id is None
    assert runner.safety_policy.allowed_tools == frozenset({"checklist", "echo"})
