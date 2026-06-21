"""Tests for deterministic decision rules."""

from __future__ import annotations

from multi_bot_agentic.decision import DeterministicDecisionEngine
from multi_bot_agentic.models import Observation
from multi_bot_agentic.safety import SafetyPolicy


def test_decision_calls_llm_before_model_output() -> None:
    """The first decision asks the selected provider for output."""

    engine = DeterministicDecisionEngine(provider_name="fake")
    decision = engine.decide(
        observations=(Observation(source="user", content="ship it"),),
        step=0,
        policy=SafetyPolicy(),
    )

    assert decision.action == "call_llm"
    assert decision.target == "fake"
    assert decision.rationale.rule_id == "observe.no-model-output"


def test_decision_routes_tool_request() -> None:
    """A TOOL-prefixed model output becomes a tool action."""

    model_observation = Observation(source="llm:fake", content="TOOL:echo:hello")
    decision = DeterministicDecisionEngine(provider_name="fake").decide(
        observations=(Observation(source="user", content="goal"), model_observation),
        step=1,
        policy=SafetyPolicy(),
    )

    assert decision.action == "call_tool"
    assert decision.target == "echo"
    assert decision.payload == {"text": "hello"}


def test_decision_sends_tool_result_back_to_model() -> None:
    """Tool results are consumed by the provider before finishing."""

    tool_observation = Observation(source="tool:echo", content="hello")
    decision = DeterministicDecisionEngine(provider_name="fake").decide(
        observations=(Observation(source="user", content="goal"), tool_observation),
        step=2,
        policy=SafetyPolicy(),
    )

    assert decision.action == "call_llm"
    assert decision.rationale.rule_id == "tool.result-needs-synthesis"
