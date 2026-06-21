"""Tests for the end-to-end Observe -> Decide -> Act runner."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.event_log import SQLiteEventLog
from multi_bot_agentic.llm.fake import FakeLLMAdapter
from multi_bot_agentic.models import EventType, ModelOutput, ModelRequest, RunState
from multi_bot_agentic.runner import AgentRunner, build_default_tools
from multi_bot_agentic.safety import SafetyPolicy


def test_runner_succeeds_with_fake_provider(tmp_path: Path) -> None:
    """The fake provider drives an end-to-end run with durable events."""

    log = SQLiteEventLog(tmp_path / "runs.sqlite")
    try:
        runner = AgentRunner(
            provider=FakeLLMAdapter(),
            event_log=log,
            tools=build_default_tools(root=tmp_path),
            safety_policy=SafetyPolicy(max_steps=5),
        )
        result = runner.run("Create an agent launch checklist", run_id="run-test")
        events = log.list_events("run-test")
    finally:
        log.close()

    assert result.state == RunState.SUCCEEDED
    assert result.answer.startswith("synthesized plan")
    assert EventType.DECISION.value in {event.event_type for event in events}
    assert EventType.ACTION_RESULT.value in {event.event_type for event in events}
    tool_events = [
        event
        for event in events
        if event.event_type == EventType.ACTION_RESULT.value and event.payload.get("kind") == "tool"
    ]
    assert tool_events[0].payload["tool"] == "checklist"


def test_runner_finishes_when_budget_hit_with_pending_tool_result(tmp_path: Path) -> None:
    """A tool result pending on the final step must finish, not fail on budget.

    With ``max_steps=3`` the fake provider's flow lands a tool result on the
    last step. Previously the ``tool.result-needs-synthesis`` rule fired before
    the budget check, the loop ran out, and the run failed with
    "step budget exhausted". It should finish via ``model.done-or-budget``.
    """

    log = SQLiteEventLog(tmp_path / "runs.sqlite")
    try:
        runner = AgentRunner(
            provider=FakeLLMAdapter(),
            event_log=log,
            tools=build_default_tools(root=tmp_path),
            safety_policy=SafetyPolicy(max_steps=3),
        )
        result = runner.run("Create an agent launch checklist", run_id="run-budget")
    finally:
        log.close()

    assert result.state == RunState.SUCCEEDED
    assert result.steps == 3


def test_runner_recovers_after_tool_failure(tmp_path: Path) -> None:
    """A failed tool result must not crash the run; the LLM gets another turn."""

    class ToolFailureProvider:
        """Provider that requests a missing file, then finishes after the tool error."""

        provider_name = "fake"

        def complete(self, request: ModelRequest, timeout_seconds: float) -> ModelOutput:
            del timeout_seconds
            tool_results = [
                observation for observation in request.observations if observation.source.startswith("tool:")
            ]
            if not tool_results:
                return ModelOutput(
                    provider=self.provider_name,
                    text="TOOL:readonly_file:missing.txt",
                    raw={"mode": "tool-failure-request"},
                )
            return ModelOutput(
                provider=self.provider_name,
                text="DONE: recovered after readonly_file failure",
                raw={"mode": "tool-failure-recovery"},
            )

    log = SQLiteEventLog(tmp_path / "runs.sqlite")
    try:
        runner = AgentRunner(
            provider=ToolFailureProvider(),
            event_log=log,
            tools=build_default_tools(root=tmp_path),
            safety_policy=SafetyPolicy(max_steps=5),
        )
        result = runner.run("Read deployment notes", run_id="run-tool-fail")
        events = log.list_events("run-tool-fail")
    finally:
        log.close()

    assert result.state == RunState.SUCCEEDED
    assert "recovered after readonly_file failure" in result.answer
    tool_events = [
        event
        for event in events
        if event.event_type == EventType.ACTION_RESULT.value and event.payload.get("kind") == "tool"
    ]
    assert tool_events
    assert tool_events[0].payload["ok"] is False


def test_runner_cancels_before_action(tmp_path: Path) -> None:
    """A cancellation file transitions the run to cancelled."""

    cancel_file = tmp_path / "cancel"
    cancel_file.write_text("stop", encoding="utf-8")
    log = SQLiteEventLog(tmp_path / "runs.sqlite")
    try:
        runner = AgentRunner(
            provider=FakeLLMAdapter(),
            event_log=log,
            tools=build_default_tools(root=tmp_path),
            safety_policy=SafetyPolicy(max_steps=5, cancellation_file=cancel_file),
        )
        result = runner.run("Create an agent launch checklist", run_id="run-cancel")
    finally:
        log.close()

    assert result.state == RunState.CANCELLED
