"""Tests for checkpoint save/load and runner resume."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from multi_bot_agentic.checkpoint import load_latest_checkpoint, save_checkpoint
from multi_bot_agentic.cli import build_parser, resume_command
from multi_bot_agentic.event_log import SQLiteEventLog
from multi_bot_agentic.llm.fake import FakeLLMAdapter
from multi_bot_agentic.models import EventType, ModelOutput, ModelRequest, Observation, RunState
from multi_bot_agentic.runner import AgentRunner, RunResult, build_default_tools
from multi_bot_agentic.safety import SafetyPolicy

TERMINAL_EVENT_TYPES = frozenset(
    {EventType.RUN_COMPLETED.value, EventType.RUN_FAILED.value, EventType.RUN_CANCELLED.value}
)


class _SimulatedCrash(BaseException):
    """Stands in for the process dying mid-step (SIGKILL, OOM, host restart).

    It is not an ``Exception``, so the runner cannot record a terminal event: the durable
    log is left exactly as a killed process would leave it.
    """


class _ScriptedProvider:
    """Provider that replays scripted replies or raises scripted errors, counting calls."""

    provider_name = "fake"

    def __init__(self, *script: str | BaseException, cancel_file: Path | None = None) -> None:
        self.script = list(script)
        self.cancel_file = cancel_file
        self.calls = 0

    def complete(self, request: ModelRequest, timeout_seconds: float) -> ModelOutput:
        del request, timeout_seconds
        self.calls += 1
        if self.cancel_file is not None:
            self.cancel_file.touch()
        item = self.script.pop(0) if self.script else "DONE: re-executed"
        if isinstance(item, BaseException):
            raise item
        return ModelOutput(provider=self.provider_name, text=item, raw={})


def _runner(
    log: SQLiteEventLog,
    tmp_path: Path,
    provider: _ScriptedProvider,
    cancel_file: Path | None = None,
) -> AgentRunner:
    """Build a runner with the checklist tool and an optional cancellation file."""

    return AgentRunner(
        provider=provider,
        event_log=log,
        tools=build_default_tools(root=tmp_path),
        safety_policy=SafetyPolicy(
            max_steps=6,
            allowed_tools=frozenset({"checklist", "echo"}),
            cancellation_file=cancel_file,
        ),
    )


def _finish_run(log: SQLiteEventLog, tmp_path: Path, outcome: str) -> RunResult:
    """Drive a real run (run id = ``outcome``) to a terminal state, leaving checkpoints behind."""

    cancel_file = tmp_path / "cancel"
    providers = {
        "succeeded": _ScriptedProvider("TOOL:checklist:ship it", "DONE: shipped"),
        "failed": _ScriptedProvider("TOOL:checklist:ship it", RuntimeError("provider outage")),
        "cancelled": _ScriptedProvider("TOOL:checklist:ship it", cancel_file=cancel_file),
    }
    result = _runner(log, tmp_path, providers[outcome], cancel_file=cancel_file).run("Ship the agent", run_id=outcome)
    cancel_file.unlink(missing_ok=True)  # the operator clears the cancel request before trying to resume
    assert result.state.value == outcome
    assert load_latest_checkpoint(log, outcome) is not None
    return result


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


def test_checkpoint_round_trips_active_bot_id(tmp_path: Path) -> None:
    """Checkpoints persist the active bot; legacy payloads without one load as ``None``."""

    log = SQLiteEventLog(tmp_path / "runs.sqlite")
    try:
        observations = (Observation(source="user", content="ship the agent"),)
        save_checkpoint(
            log,
            run_id="run-bot",
            goal="ship the agent",
            step=1,
            state=RunState.ACTING,
            observations=observations,
            active_bot_id="writer",
        )
        save_checkpoint(
            log,
            run_id="run-no-bot",
            goal="ship the agent",
            step=1,
            state=RunState.ACTING,
            observations=observations,
        )
        with_bot = load_latest_checkpoint(log, "run-bot")
        without_bot = load_latest_checkpoint(log, "run-no-bot")
        legacy_payload = log.list_events("run-no-bot")[-1].payload
    finally:
        log.close()

    assert with_bot is not None
    assert with_bot.active_bot_id == "writer"
    assert without_bot is not None
    assert without_bot.active_bot_id is None
    assert "active_bot_id" not in legacy_payload


@pytest.mark.parametrize("outcome", ["succeeded", "failed", "cancelled"])
def test_resume_of_a_finished_run_executes_nothing_and_returns_the_recorded_outcome(
    tmp_path: Path,
    outcome: str,
) -> None:
    """A finished run is final: ``resume`` must not run new steps or append events.

    ``resume`` used to restart the loop from the latest checkpoint with a fresh state
    machine, so a succeeded run logged a second ``run_completed``, and failed or cancelled
    runs called the provider again (a cancelled run even ran its pending tool call) and
    ended as succeeded. It must instead return the recorded outcome, idempotently, with
    ``already_finished=True``.
    """

    log = SQLiteEventLog(tmp_path / "runs.sqlite")
    try:
        original = _finish_run(log, tmp_path, outcome)
        before = log.list_events(outcome)
        provider = _ScriptedProvider("DONE: re-executed")
        runner = _runner(log, tmp_path, provider)
        first = runner.resume(outcome)
        second = runner.resume(outcome)
        appended = log.list_events(outcome)[len(before) :]
    finally:
        log.close()

    assert [event.event_type for event in appended] == []
    assert provider.calls == 0
    assert first == second == replace(original, already_finished=True)


def test_resume_continues_an_interrupted_run_exactly_once(tmp_path: Path) -> None:
    """A run whose process died mid-step still resumes; resuming it again is a no-op."""

    log = SQLiteEventLog(tmp_path / "runs.sqlite")
    try:
        crashing = _runner(log, tmp_path, _ScriptedProvider("TOOL:checklist:ship it", _SimulatedCrash()))
        with pytest.raises(_SimulatedCrash):
            crashing.run("Ship the agent", run_id="crashed")
        interrupted = log.list_events("crashed")
        provider = _ScriptedProvider("DONE: finished after the crash")
        runner = _runner(log, tmp_path, provider)
        resumed = runner.resume("crashed")
        after_resume = log.list_events("crashed")
        again = runner.resume("crashed")
        after_again = log.list_events("crashed")
    finally:
        log.close()

    assert not any(event.event_type in TERMINAL_EVENT_TYPES for event in interrupted)
    assert (resumed.state, resumed.answer) == (RunState.SUCCEEDED, "finished after the crash")
    assert provider.calls == 1
    assert [event.event_type for event in after_again[len(after_resume) :]] == []
    assert [event.event_type for event in after_resume].count(EventType.RUN_COMPLETED.value) == 1
    assert resumed.already_finished is False
    assert again == replace(resumed, already_finished=True)


@pytest.mark.parametrize(("outcome", "exit_code"), [("succeeded", 0), ("failed", 2), ("cancelled", 2)])
def test_cli_resume_of_a_finished_run_reports_the_recorded_outcome(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    outcome: str,
    exit_code: int,
) -> None:
    """CLI ``resume`` on a finished run executes nothing and prints ``"resumed": false``.

    The exit code follows the recorded state, like ``run``: 0 for succeeded, 2 otherwise.
    """

    event_log = tmp_path / "runs.sqlite"
    log = SQLiteEventLog(event_log)
    try:
        original = _finish_run(log, tmp_path, outcome)
        before = log.list_events(outcome)
    finally:
        log.close()
    args = build_parser().parse_args(
        ["resume", "--run-id", outcome, "--event-log", str(event_log), "--provider", "fake"]
    )

    code = resume_command(args)
    captured = capsys.readouterr()
    log = SQLiteEventLog(event_log)
    try:
        appended = log.list_events(outcome)[len(before) :]
    finally:
        log.close()

    assert [event.event_type for event in appended] == []
    assert code == exit_code
    payload = json.loads(captured.out)
    assert payload["resumed"] is False
    assert (payload["state"], payload["answer"], payload["steps"]) == (
        original.state.value,
        original.answer,
        original.steps,
    )
    assert f"run {outcome} already finished ({outcome}); nothing to resume" in captured.err


@pytest.mark.parametrize("unavailable", ["mcp-server", "provider-credentials"])
def test_cli_resume_of_a_finished_run_needs_no_runtime_dependencies(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    unavailable: str,
) -> None:
    """A finished run's outcome is read before any MCP server or provider is started.

    Resuming stays idempotent even when the run's runtime dependencies are gone: an MCP
    server that can no longer start, or provider credentials that were removed.
    """

    event_log = tmp_path / "runs.sqlite"
    log = SQLiteEventLog(event_log)
    try:
        original = _finish_run(log, tmp_path, "succeeded")
        before = log.list_events("succeeded")
    finally:
        log.close()
    argv = ["resume", "--run-id", "succeeded", "--event-log", str(event_log)]
    if unavailable == "mcp-server":
        config = tmp_path / "mcp.json"
        config.write_text(
            json.dumps({"mcpServers": {"gone": {"command": str(tmp_path / "missing-server")}}}),
            encoding="utf-8",
        )
        argv += ["--provider", "fake", "--mcp-config", str(config)]
    else:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        argv += ["--provider", "openai"]

    code = resume_command(build_parser().parse_args(argv))
    captured = capsys.readouterr()
    log = SQLiteEventLog(event_log)
    try:
        appended = log.list_events("succeeded")[len(before) :]
    finally:
        log.close()

    assert code == 0, captured.err
    assert [event.event_type for event in appended] == []
    payload = json.loads(captured.out)
    assert (payload["state"], payload["answer"], payload["resumed"]) == ("succeeded", original.answer, False)
