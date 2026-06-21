"""Tests for the end-to-end Observe -> Decide -> Act runner."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.event_log import SQLiteEventLog
from multi_bot_agentic.llm.fake import FakeLLMAdapter
from multi_bot_agentic.models import EventType, RunState
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
