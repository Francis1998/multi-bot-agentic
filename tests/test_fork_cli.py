"""CLI tests for ``history`` and ``fork``, and for fork lineage in ``report``, ``replay``, and ``trace``."""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections.abc import Callable
from pathlib import Path

import pytest

from multi_bot_agentic import cli
from multi_bot_agentic.cli import (
    build_parser,
    fork_command,
    history_command,
    replay_command,
    report_command,
    run_command,
    trace_command,
)
from multi_bot_agentic.event_log import SQLiteEventLog
from multi_bot_agentic.llm.fake import FakeLLMAdapter
from multi_bot_agentic.tracing.spans import span_id_for, trace_id_for

GOAL = "Create a launch checklist"
NEW_GOAL = "Create a rollback checklist"
EXAMPLE_BOTS = Path(__file__).resolve().parents[1] / "examples" / "bots" / "release-crew.json"
COMMANDS: dict[str, Callable[[argparse.Namespace], int]] = {
    "run": run_command,
    "fork": fork_command,
    "history": history_command,
    "report": report_command,
    "replay": replay_command,
    "trace": trace_command,
}


@pytest.fixture(autouse=True)
def _hermetic_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("MULTIBOT_PROVIDER", "MULTIBOT_MAX_STEPS", "MULTIBOT_FAKE_TOOL", "MULTIBOT_CANCEL_FILE"):
        monkeypatch.delenv(name, raising=False)


def _invoke(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, str, str]:
    args = build_parser().parse_args(list(argv))
    code = COMMANDS[args.command](args)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def _record_demo(event_log: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, _, _ = _invoke(
        capsys, "run", "--goal", GOAL, "--provider", "fake", "--event-log", str(event_log), "--run-id", "demo"
    )
    assert code == 0


def _fork_rollback(event_log: Path, capsys: pytest.CaptureFixture[str]) -> tuple[int, str, str]:
    return _invoke(
        capsys,
        "fork",
        "--event-log",
        str(event_log),
        "--run-id",
        "demo",
        "--at-step",
        "1",
        "--new-run-id",
        "rollback",
        "--goal",
        NEW_GOAL,
        "--provider",
        "fake",
    )


def _all_events(event_log: Path) -> list[tuple[str, int]]:
    log = SQLiteEventLog(event_log)
    try:
        return [(event.run_id, event.seq) for event in log.list_events()]
    finally:
        log.close()


def test_history_lists_the_steps_a_fork_can_continue_after(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """``history`` prints one row per step with its bot, action, rule, outcome, and whether it is forkable."""

    event_log = tmp_path / "runs.sqlite"
    _record_demo(event_log, capsys)

    code, out, err = _invoke(capsys, "history", "--event-log", str(event_log))
    json_code, json_out, _ = _invoke(
        capsys, "history", "--event-log", str(event_log), "--run-id", "demo", "--format", "json"
    )

    assert code == 0
    assert err == "note: --run-id not given; showing the most recent run demo\n"
    assert out.splitlines() == [
        "run demo: succeeded after 4 steps (provider fake)",
        "goal: Create a launch checklist",
        "step  bot  action     target     rule                         outcome         fork",
        "   0  -    start      -          -                            -               yes",
        "   1  -    call_llm   fake       observe.no-model-output      TOOL checklist  yes",
        "   2  -    call_tool  checklist  model.requested-tool         checklist ok    yes",
        "   3  -    call_llm   fake       tool.result-needs-synthesis  DONE            yes",
        "   4  -    finish     -          model.done-or-budget         succeeded       no",
        "forkable steps: 0, 1, 2, 3",
    ]
    history = json.loads(json_out)
    assert json_code == 0
    assert (history["final_state"], history["last_step"], history["forkable_steps"]) == ("succeeded", 4, [0, 1, 2, 3])


def test_fork_dry_run_prints_the_rebuilt_state_and_writes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """``--dry-run`` shows the state after the step, the overrides, and the first decision, then stops."""

    event_log = tmp_path / "runs.sqlite"
    _record_demo(event_log, capsys)
    before = _all_events(event_log)

    code, out, _ = _invoke(
        capsys,
        "fork",
        "--event-log",
        str(event_log),
        "--run-id",
        "demo",
        "--at-step",
        "1",
        "--new-run-id",
        "rollback",
        "--goal",
        NEW_GOAL,
        "--dry-run",
    )
    plan = json.loads(out)

    assert code == 0
    assert _all_events(event_log) == before
    assert (plan["dry_run"], plan["fork_step"], plan["max_steps"], plan["remaining_steps"]) == (True, 1, 6, 5)
    assert plan["overrides"] == {"goal": NEW_GOAL}
    assert [(item["source"], item["content"]) for item in plan["observations"]] == [
        ("user", GOAL),
        ("llm:fake", f"TOOL:checklist:{GOAL}"),
        ("user", NEW_GOAL),
    ]
    assert plan["next_decision"] == {"action": "call_llm", "target": "fake", "rule_id": "observe.new-user-goal"}


def test_fork_continues_and_report_shows_parents_children_and_tampering(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """``report`` shows lineage both ways and re-checks the inherited events against their digest."""

    event_log = tmp_path / "runs.sqlite"
    _record_demo(event_log, capsys)

    code, out, err = _fork_rollback(event_log, capsys)
    _, parent_report, _ = _invoke(capsys, "report", "--event-log", str(event_log), "--run-id", "demo")
    _, child_report, _ = _invoke(capsys, "report", "--event-log", str(event_log), "--run-id", "rollback")
    _, full_report, _ = _invoke(capsys, "report", "--event-log", str(event_log))

    assert code == 0
    assert err == "note: forked run demo after step 1 into rollback (9 events inherited; new goal)\n"
    assert json.loads(out) == {
        "run_id": "rollback",
        "parent_run_id": "demo",
        "fork_step": 1,
        "state": "succeeded",
        "answer": "synthesized plan from 5 observations",
        "steps": 5,
        "event_log": str(event_log),
    }
    assert json.loads(parent_report)["runs"][0]["lineage"] == {
        "parent": None,
        "children": [{"run_id": "rollback", "fork_step": 1, "overrides": {"goal": NEW_GOAL}}],
    }
    parent = json.loads(child_report)["runs"][0]["lineage"]["parent"]
    assert (parent["parent_run_id"], parent["fork_step"], parent["inherited_events"]) == ("demo", 1, 9)
    assert parent["inherited_events_verified"] is True
    assert [run.get("lineage") is not None for run in json.loads(full_report)["runs"]] == [True, True]

    with sqlite3.connect(event_log) as connection:
        connection.execute(
            "UPDATE events SET payload_json = ? WHERE run_id = 'rollback' AND seq = 2",
            (json.dumps({"goal": "edited later", "provider": "fake"}),),
        )
    _, tampered, _ = _invoke(capsys, "report", "--event-log", str(event_log), "--run-id", "rollback")
    assert json.loads(tampered)["runs"][0]["lineage"]["parent"]["inherited_events_verified"] is False


def test_replay_report_history_and_trace_of_a_fork_never_call_a_provider(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reading a fork needs only the event log: no adapter is built and no model is called."""

    event_log = tmp_path / "runs.sqlite"
    _record_demo(event_log, capsys)
    assert _fork_rollback(event_log, capsys)[0] == 0

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("a provider was used while reading a fork")

    monkeypatch.setattr(cli, "build_llm_adapter", forbidden)
    monkeypatch.setattr(FakeLLMAdapter, "complete", forbidden)
    base = ["--event-log", str(event_log), "--run-id", "rollback"]

    replay = _invoke(capsys, "replay", *base, "--format", "text")
    report = _invoke(capsys, "report", *base)
    history = _invoke(capsys, "history", *base)
    otlp = _invoke(capsys, "trace", *base)
    mermaid = _invoke(capsys, "trace", *base, "--format", "mermaid")

    assert [result[0] for result in (replay, report, history, otlp, mermaid)] == [0, 0, 0, 0, 0]
    assert replay[1].splitlines()[0] == "001 created    run_forked parent=demo step=1 inherited=9"
    assert "forked from demo after step 1 (new goal); * = inherited" in history[1]
    root = json.loads(otlp[1])["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
    assert [(link["traceId"], link["spanId"]) for link in root["links"]] == [
        (trace_id_for("demo"), span_id_for("demo", "root"))
    ]
    assert "Note over O: forked from demo after step 1 (new goal)" in mermaid[1]


def test_fork_with_the_example_bot_registry_continues_as_the_writer(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """``--bots`` registers the bundled release crew; ``--bot writer`` limits the fork to echo."""

    event_log = tmp_path / "runs.sqlite"
    _record_demo(event_log, capsys)
    monkeypatch.setenv("MULTIBOT_FAKE_TOOL", "echo")

    code, out, _ = _invoke(
        capsys,
        "fork",
        "--event-log",
        str(event_log),
        "--run-id",
        "demo",
        "--at-step",
        "1",
        "--new-run-id",
        "notes",
        "--bots",
        str(EXAMPLE_BOTS),
        "--bot",
        "writer",
    )
    _, history, _ = _invoke(capsys, "history", "--event-log", str(event_log), "--run-id", "notes", "--format", "json")
    steps = json.loads(history)["steps"]

    assert (code, json.loads(out)["state"]) == (0, "succeeded")
    assert [(step["bot"], step["outcome"]) for step in steps[2:]] == [
        ("writer", "TOOL echo"),
        ("writer", "echo ok"),
        ("writer", "DONE"),
        ("writer", "succeeded"),
    ]


@pytest.mark.parametrize(
    ("extra", "message"),
    [
        (["--at-step", "4"], "error: step 4 ended run demo (finish -> succeeded); forkable steps: 0, 1, 2, 3"),
        (["--at-step", "1", "--bot", "writer"], "error: --bot needs --bots PATH"),
        (["--at-step", "1", "--provider", "nope"], "error: unsupported provider: nope"),
        (["--at-step", "1", "--max-steps", "0"], "error: max_steps must be >= 1, got 0"),
        (["--at-step", "1", "--bots", "bad.json"], "is not valid JSON"),
        (["--at-step", "1", "--dry-run", "--new-run-id", "demo"], "error: run demo already exists"),
    ],
)
def test_fork_errors_exit_2_and_write_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, extra: list[str], message: str
) -> None:
    """Every refused fork prints one ``error:`` line, exits 2, and leaves the log unchanged."""

    event_log = tmp_path / "runs.sqlite"
    _record_demo(event_log, capsys)
    (tmp_path / "bad.json").write_text("{not json", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    before = _all_events(event_log)
    argv = ["fork", "--event-log", str(event_log), "--run-id", "demo", "--new-run-id", "branch", *extra]

    code, out, err = _invoke(capsys, *argv)

    assert (code, out) == (2, "")
    assert message in err
    assert _all_events(event_log) == before


@pytest.mark.parametrize("command", ["history", "fork"])
def test_a_missing_event_log_is_reported_and_never_created(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], command: str
) -> None:
    """``history`` and ``fork`` read an existing log only."""

    missing = tmp_path / "missing.sqlite"
    argv = [command, "--event-log", str(missing), "--run-id", "demo"]
    if command == "fork":
        argv += ["--at-step", "1", "--new-run-id", "branch"]

    code, _, err = _invoke(capsys, *argv)

    assert (code, err) == (2, f"error: event log not found: {missing}\n")
    assert not missing.exists()
