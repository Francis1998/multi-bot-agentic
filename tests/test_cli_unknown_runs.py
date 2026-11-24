"""Regression tests: a run id the event log doesn't hold is one clean CLI error, never a traceback.

``resume --run-id <unknown>`` crashed with ``ValueError: no checkpoint found for run_id=...`` (exit 1),
and ``replay`` and ``report`` exited 0 with no events or ``{"runs": []}``, as if the run existed but was
empty. ``resume`` also crashed on runs it cannot continue. The CLI runs in a subprocess here, as a user
runs it, so a traceback would reach stderr.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from multi_bot_agentic.checkpoint import save_checkpoint
from multi_bot_agentic.cli import build_parser, run_command
from multi_bot_agentic.event_log import SQLiteEventLog
from multi_bot_agentic.llm.fake import FakeLLMAdapter
from multi_bot_agentic.models import EventType, Observation, RunState
from multi_bot_agentic.runner import AgentRunner, build_default_tools
from multi_bot_agentic.safety import SafetyPolicy

SRC = Path(__file__).resolve().parents[1] / "src"
GOAL = "Create a launch checklist"
UNKNOWN = "does-not-exist"
# Every command that reads one run by --run-id, with the arguments it needs besides --event-log.
LOOKUPS: dict[str, tuple[str, ...]] = {
    "resume": ("--run-id", UNKNOWN, "--provider", "fake"),
    "replay": ("--run-id", UNKNOWN),
    "report": ("--run-id", UNKNOWN),
    "history": ("--run-id", UNKNOWN),
    "trace": ("--run-id", UNKNOWN),
    "fork": ("--run-id", UNKNOWN, "--at-step", "1", "--new-run-id", "branch", "--provider", "fake"),
}


@pytest.fixture(autouse=True)
def _hermetic_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in [name for name in os.environ if name.startswith("MULTIBOT_")]:
        monkeypatch.delenv(name)


def _cli(*argv: str) -> subprocess.CompletedProcess[str]:
    """Run ``multi-bot-agentic <argv>`` in a fresh interpreter."""

    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(filter(None, (str(SRC), env.get("PYTHONPATH"))))
    return subprocess.run(
        [sys.executable, "-m", "multi_bot_agentic.cli", *argv],
        capture_output=True,
        check=False,
        env=env,
        text=True,
        timeout=120,
    )


def _record(event_log: Path, *run_ids: str) -> None:
    """Record one finished fake-provider run per id, in order (the last one is the most recent)."""

    for run_id in run_ids:
        args = build_parser().parse_args(
            ["run", "--goal", GOAL, "--provider", "fake", "--event-log", str(event_log), "--run-id", run_id]
        )
        assert run_command(args) == 0


def _events(event_log: Path) -> list[tuple[str, int]]:
    log = SQLiteEventLog(event_log)
    try:
        return [(event.run_id, event.seq) for event in log.list_events()]
    finally:
        log.close()


@pytest.mark.parametrize("command", list(LOOKUPS))
def test_an_unknown_run_id_is_one_error_line_with_exit_code_2(tmp_path: Path, command: str) -> None:
    """The error names the missing run, the log, and the runs it does hold; nothing is printed or written."""

    event_log = tmp_path / "runs.sqlite"
    _record(event_log, "demo")
    before = _events(event_log)

    result = _cli(command, "--event-log", str(event_log), *LOOKUPS[command])

    assert "Traceback" not in result.stderr, result.stderr
    assert (result.returncode, result.stdout) == (2, "")
    assert result.stderr.splitlines() == [
        f"error: run {UNKNOWN} not found in event log {event_log} (recent runs: demo)"
    ]
    assert _events(event_log) == before


@pytest.mark.parametrize(
    ("recorded", "hint"),
    [
        ((), "the log has no runs"),
        (("first", "second"), "recent runs: second, first"),
        (
            tuple(f"run-{number}" for number in range(1, 8)),
            "recent runs: run-7, run-6, run-5, run-4, run-3, and 2 more",
        ),
    ],
)
def test_the_error_lists_up_to_five_runs_most_recent_first(
    tmp_path: Path, recorded: tuple[str, ...], hint: str
) -> None:
    """A mistyped id is easy to correct, and a long log keeps the error on one short line."""

    event_log = tmp_path / "runs.sqlite"
    SQLiteEventLog(event_log).close()
    _record(event_log, *recorded)

    result = _cli("history", "--event-log", str(event_log), "--run-id", UNKNOWN)

    assert (result.returncode, result.stdout) == (2, "")
    assert result.stderr == f"error: run {UNKNOWN} not found in event log {event_log} ({hint})\n"


@pytest.mark.parametrize(
    ("run_id", "message"),
    [
        (
            "died-in-step-0",
            "error: cannot resume run died-in-step-0: it has no checkpoint (it stopped before its first step finished)",
        ),
        (
            "forked-as-writer",
            "error: cannot resume run forked-as-writer: checkpoint active bot is not registered: writer",
        ),
    ],
)
def test_resume_of_a_run_it_cannot_continue_is_one_error_line_with_exit_code_2(
    tmp_path: Path, run_id: str, message: str
) -> None:
    """Interrupted runs without a usable checkpoint are refused cleanly, and nothing is appended.

    ``died-in-step-0`` was killed before its first checkpoint. ``forked-as-writer`` was killed after a
    checkpoint that records the ``writer`` bot (as ``fork --bot writer`` does), and ``resume`` has no
    bot registry to restore its scope from.
    """

    event_log = tmp_path / "runs.sqlite"
    log = SQLiteEventLog(event_log)
    try:
        log.append(run_id, RunState.CREATED, EventType.RUN_CREATED, {"goal": GOAL, "provider": "fake"})
        if run_id == "forked-as-writer":
            save_checkpoint(
                log,
                run_id=run_id,
                goal=GOAL,
                step=1,
                state=RunState.ACTING,
                observations=(Observation(source="user", content=GOAL),),
                active_bot_id="writer",
            )
    finally:
        log.close()
    before = _events(event_log)

    result = _cli("resume", "--run-id", run_id, "--event-log", str(event_log), "--provider", "fake")

    assert "Traceback" not in result.stderr, result.stderr
    assert (result.returncode, result.stdout) == (2, "")
    assert result.stderr.splitlines() == [message]
    assert _events(event_log) == before


def test_runner_resume_of_an_unknown_run_raises_run_not_found_error(tmp_path: Path) -> None:
    """Library callers get a dedicated ``ValueError`` subclass that names the run and the log."""

    from multi_bot_agentic.runner import ResumeError, RunNotFoundError

    log = SQLiteEventLog(tmp_path / "runs.sqlite")
    try:
        runner = AgentRunner(
            provider=FakeLLMAdapter(),
            event_log=log,
            tools=build_default_tools(root=tmp_path),
            safety_policy=SafetyPolicy(),
        )
        with pytest.raises(RunNotFoundError) as raised:
            runner.resume(UNKNOWN)
        events = log.list_events()
    finally:
        log.close()

    assert str(raised.value) == f"run {UNKNOWN} not found in event log {tmp_path / 'runs.sqlite'}"
    assert isinstance(raised.value, ResumeError)
    assert isinstance(raised.value, ValueError)
    assert events == []
