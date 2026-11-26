"""Regression tests: ``run`` never appends a new run to a run id the event log already holds.

Running the README quickstart twice (``run --run-id demo`` against the same ``--event-log``) exited 0
and appended the second run's events to ``demo``. The log then held two ``run_created`` events under
one run id: ``history`` showed the first run's goal next to the second run's steps, ``report`` counted
both runs' decisions and tool calls, and ``fork --at-step 1`` branched from the second run's state while
inheriting the first run's ``run_completed`` event. ``fork`` already refuses an existing
``--new-run-id``; ``run`` must refuse an existing ``--run-id`` the same way, before anything is written.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from multi_bot_agentic.event_log import SQLiteEventLog
from multi_bot_agentic.llm.fake import FakeLLMAdapter
from multi_bot_agentic.models import EventType, RunState
from multi_bot_agentic.runner import AgentRunner, build_default_tools
from multi_bot_agentic.safety import SafetyPolicy

SRC = Path(__file__).resolve().parents[1] / "src"
MCP_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "mcp"
GOAL = "Create a launch checklist"
OTHER_GOAL = "Plan a database migration"


@pytest.fixture(autouse=True)
def _hermetic_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in [name for name in os.environ if name.startswith("MULTIBOT_")]:
        monkeypatch.delenv(name)


def _cli(*argv: str) -> subprocess.CompletedProcess[str]:
    """Run ``multi-bot-agentic <argv>`` in a fresh interpreter, as a user runs it."""

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


def _run(event_log: Path, run_id: str, goal: str, *extra: str) -> subprocess.CompletedProcess[str]:
    """``multi-bot-agentic run`` (fake provider unless ``extra`` picks another one)."""

    return _cli("run", "--goal", goal, "--event-log", str(event_log), "--run-id", run_id, "--provider", "fake", *extra)


def _events(event_log: Path) -> list[tuple[str, int, str]]:
    log = SQLiteEventLog(event_log)
    try:
        return [(event.run_id, event.seq, event.event_type) for event in log.list_events()]
    finally:
        log.close()


def _refusal(run_id: str, event_log: Path) -> str:
    return (
        f"error: run {run_id} already exists in event log {event_log}; "
        "choose a new --run-id (resume continues an interrupted run)"
    )


def _record_interrupted(event_log: Path, run_id: str) -> None:
    """Record a run that was created but never finished, as if its process was killed."""

    log = SQLiteEventLog(event_log)
    try:
        log.append(run_id, RunState.CREATED, EventType.RUN_CREATED, {"goal": GOAL, "provider": "fake"})
    finally:
        log.close()


@pytest.mark.parametrize("recorded", ["finished", "interrupted"])
def test_run_refuses_a_run_id_the_log_already_holds_and_writes_nothing(tmp_path: Path, recorded: str) -> None:
    """Re-running ``run --run-id demo`` is one error line with exit code 2, and ``demo`` keeps only its own events."""

    event_log = tmp_path / "runs.sqlite"
    if recorded == "finished":
        assert _run(event_log, "demo", GOAL).returncode == 0
    else:
        _record_interrupted(event_log, "demo")
    before = _events(event_log)

    result = _run(event_log, "demo", OTHER_GOAL)

    assert (result.returncode, result.stdout) == (2, "")
    assert result.stderr.splitlines() == [_refusal("demo", event_log)]
    assert _events(event_log) == before


@pytest.mark.parametrize("setup", ["broken-mcp-server", "working-mcp-server", "missing-credentials"])
def test_an_existing_run_id_is_refused_before_mcp_servers_or_the_provider_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, setup: str
) -> None:
    """The refusal is not hidden behind an MCP or provider setup error, nor mixed with ``mcp:`` status lines."""

    event_log = tmp_path / "runs.sqlite"
    assert _run(event_log, "demo", GOAL).returncode == 0
    before = _events(event_log)
    if setup == "missing-credentials":
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        extra = ["--provider", "openai"]
    else:
        server = [str(tmp_path / "missing-server")]
        if setup == "working-mcp-server":
            server = [sys.executable, str(MCP_FIXTURES / "modern_server.py")]
        config = tmp_path / "mcp.json"
        config.write_text(
            json.dumps({"mcpServers": {"notes": {"command": server[0], "args": server[1:]}}}), encoding="utf-8"
        )
        extra = ["--mcp-config", str(config)]

    result = _run(event_log, "demo", OTHER_GOAL, *extra)

    assert (result.returncode, result.stdout) == (2, "")
    assert result.stderr.splitlines() == [_refusal("demo", event_log)]
    assert _events(event_log) == before


def test_runner_run_refuses_a_run_id_the_log_already_holds(tmp_path: Path) -> None:
    """Library callers get a ``ValueError`` naming the run and the log, and nothing is appended."""

    path = tmp_path / "runs.sqlite"
    log = SQLiteEventLog(path)
    try:
        runner = AgentRunner(
            provider=FakeLLMAdapter(),
            event_log=log,
            tools=build_default_tools(root=tmp_path),
            safety_policy=SafetyPolicy(max_steps=5),
        )
        runner.run(GOAL, run_id="demo")
        before = log.list_events()
        with pytest.raises(ValueError, match="already exists") as raised:
            runner.run(OTHER_GOAL, run_id="demo")
        after = log.list_events()
    finally:
        log.close()

    assert str(raised.value) == (
        f"run demo already exists in event log {path}; choose a new run id (resume continues an interrupted run)"
    )
    assert after == before
