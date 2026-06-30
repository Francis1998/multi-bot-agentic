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


def test_decision_retries_model_after_malformed_tool_request() -> None:
    """A malformed tool request asks the provider for a corrected action."""

    model_observation = Observation(source="llm:fake", content="TOOL:echo")
    decision = DeterministicDecisionEngine(provider_name="fake").decide(
        observations=(Observation(source="user", content="goal"), model_observation),
        step=1,
        policy=SafetyPolicy(),
    )

    assert decision.action == "call_llm"
    assert decision.target == "fake"
    assert decision.payload == {"reason": "malformed tool request"}
    assert decision.rationale.rule_id == "model.malformed-tool-request"


def test_decision_finishes_on_final_step_with_pending_tool_result() -> None:
    """On the final step a pending tool result finishes instead of re-calling the model."""

    tool_observation = Observation(source="tool:checklist", content="checklist body")
    decision = DeterministicDecisionEngine(provider_name="fake").decide(
        observations=(Observation(source="user", content="goal"), tool_observation),
        step=2,
        policy=SafetyPolicy(max_steps=3),
    )

    assert decision.action == "finish"
    assert decision.rationale.rule_id == "model.done-or-budget"
    assert decision.payload == {"answer": "checklist body"}


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
