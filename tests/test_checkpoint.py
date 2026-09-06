"""Tests for checkpoint save/load and runner resume."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.checkpoint import load_latest_checkpoint, save_checkpoint
from multi_bot_agentic.event_log import SQLiteEventLog
from multi_bot_agentic.llm.fake import FakeLLMAdapter
from multi_bot_agentic.models import EventType, ModelOutput, ModelRequest, Observation, RunState
from multi_bot_agentic.runner import AgentRunner, build_default_tools
from multi_bot_agentic.safety import SafetyPolicy


def test_save_and_load_latest_checkpoint_restores_observations_and_step(tmp_path: Path) -> None:
    """Checkpoint payloads round-trip observations and the next step index."""

    log = SQLiteEventLog(tmp_path / "runs.sqlite")
    try:
        observations = (
            Observation(source="user", content="ship the agent"),
            Observation(source="llm:fake", content="TOOL:checklist:ship the agent"),
        )
        saved = save_checkpoint(
            log,
            run_id="run-ckpt",
            goal="ship the agent",
            step=2,
            state=RunState.ACTING,
            observations=observations,
        )
        loaded = load_latest_checkpoint(log, "run-ckpt")
    finally:
        log.close()

    assert saved.step == 2
    assert loaded is not None
    assert loaded.goal == "ship the agent"
    assert loaded.step == 2
    assert loaded.state == RunState.ACTING
    assert len(loaded.observations) == 2
    assert loaded.observations[0].content == "ship the agent"
    assert loaded.observations[1].source == "llm:fake"


def test_resume_restores_observations_and_continues_run(tmp_path: Path) -> None:
    """resume() restores checkpoint observations/step and finishes the run."""

    class ResumeProvider:
        """Provider that finishes once resumed observations are present."""

        provider_name = "fake"

        def complete(self, request: ModelRequest, timeout_seconds: float) -> ModelOutput:
            del timeout_seconds
            assert any(item.content == "paused mid-run" for item in request.observations)
            return ModelOutput(
                provider=self.provider_name,
                text="DONE: resumed successfully",
                raw={"mode": "resume-finish"},
            )

    log = SQLiteEventLog(tmp_path / "runs.sqlite")
    try:
        log.append(
            "run-resume",
            RunState.CREATED,
            EventType.RUN_CREATED,
            {"goal": "continue the mission", "provider": "fake"},
        )
        save_checkpoint(
            log,
            run_id="run-resume",
            goal="continue the mission",
            step=1,
            state=RunState.ACTING,
            observations=(
                Observation(source="user", content="continue the mission"),
                Observation(source="system", content="paused mid-run"),
            ),
        )
        runner = AgentRunner(
            provider=ResumeProvider(),
            event_log=log,
            tools=build_default_tools(root=tmp_path),
            safety_policy=SafetyPolicy(max_steps=5, allowed_tools=frozenset({"checklist", "echo"})),
        )
        result = runner.resume("run-resume")
        loaded = load_latest_checkpoint(log, "run-resume")
    finally:
        log.close()

    assert result.state == RunState.SUCCEEDED
    assert result.answer == "resumed successfully"
    assert loaded is not None
    assert any(item.content == "paused mid-run" for item in loaded.observations)


def test_run_emits_checkpoint_events(tmp_path: Path) -> None:
    """A normal run writes checkpoint events into the durable log."""

    log = SQLiteEventLog(tmp_path / "runs.sqlite")
    try:
        runner = AgentRunner(
            provider=FakeLLMAdapter(),
            event_log=log,
            tools=build_default_tools(root=tmp_path),
            safety_policy=SafetyPolicy(max_steps=5),
        )
        result = runner.run("Create an agent launch checklist", run_id="run-with-ckpt")
        events = log.list_events("run-with-ckpt")
    finally:
        log.close()

    assert result.state == RunState.SUCCEEDED
    assert any(event.event_type == EventType.CHECKPOINT.value for event in events)
