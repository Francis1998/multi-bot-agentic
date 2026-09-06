"""Tests for typed multi-bot handoff parsing and isolation."""

from __future__ import annotations

from pathlib import Path

import pytest

from multi_bot_agentic.bots import BotSpec
from multi_bot_agentic.decision import DeterministicDecisionEngine
from multi_bot_agentic.event_log import SQLiteEventLog
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
