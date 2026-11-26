"""End-to-end CLI tests for approval interrupts with the fake provider."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from multi_bot_agentic import cli
from multi_bot_agentic.event_log import SQLiteEventLog

GOAL = "Create a launch checklist"


@pytest.fixture(autouse=True)
def _hermetic_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "MULTIBOT_PROVIDER",
        "MULTIBOT_MAX_STEPS",
        "MULTIBOT_FAKE_TOOL",
        "MULTIBOT_CANCEL_FILE",
        "MULTIBOT_REQUIRE_APPROVAL",
    ):
        monkeypatch.delenv(name, raising=False)


def _cli(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, str, str]:
    code = cli.main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def _start(capsys: pytest.CaptureFixture[str], log: Path, run_id: str = "demo", *extra: str) -> dict[str, object]:
    code, out, err = _cli(
        capsys, "run", "--goal", GOAL, "--provider", "fake", "--event-log", str(log), "--run-id", run_id, *extra
    )
    assert code == 3, err
    assert f"note: run {run_id} paused in step 2: checklist needs approval" in err
    payload: dict[str, object] = json.loads(out)
    return payload


def _tool_results(log: Path, run_id: str) -> int:
    event_log = SQLiteEventLog(log)
    try:
        events = event_log.list_events(run_id)
    finally:
        event_log.close()
    return sum(1 for event in events if event.event_type == "action_result" and event.payload.get("kind") == "tool")


def test_run_pause_approve_with_edit_and_resume(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    log = tmp_path / "runs.sqlite"
    paused = _start(capsys, log, "demo", "--require-approval", "checklist")
    assert paused["state"] == "awaiting_approval"
    interrupt = paused["interrupt"]
    assert isinstance(interrupt, dict)
    interrupt_id = str(interrupt["interrupt_id"])
    assert interrupt["tool"] == "checklist" and interrupt["step"] == 2

    code, out, _ = _cli(capsys, "approvals", "list", "--event-log", str(log))
    assert code == 0 and interrupt_id in out and "pending" in out
    code, out, _ = _cli(capsys, "approvals", "show", interrupt_id, "--event-log", str(log), "--format", "json")
    assert code == 0 and json.loads(out)["arguments"] == {"text": GOAL}

    code, _, err = _cli(capsys, "resume", "--run-id", "demo", "--event-log", str(log))
    assert code == 3 and "is awaiting approval" in err and _tool_results(log, "demo") == 0

    edited = json.dumps({"text": "Create a launch checklist with a rollback plan"})
    code, out, err = _cli(
        capsys, "approve", interrupt_id, "--event-log", str(log), "--by", "alice", "--reason", "ok", "--args", edited
    )
    assert code == 0, err
    decided = json.loads(out)
    assert decided["status"] == "approved"
    assert decided["decision"]["decided_by"] == "alice" and decided["decision"]["args_edited"] is True
    code, _, err = _cli(capsys, "reject", interrupt_id, "--event-log", str(log), "--reason", "late")
    assert code == 2 and "already approved by alice" in err

    code, out, _ = _cli(capsys, "resume", "--run-id", "demo", "--event-log", str(log))
    assert code == 0 and json.loads(out)["state"] == "succeeded"
    assert _tool_results(log, "demo") == 1
    code, _, err = _cli(capsys, "resume", "--run-id", "demo", "--event-log", str(log))
    assert code == 0 and "already finished" in err and _tool_results(log, "demo") == 1

    code, out, _ = _cli(capsys, "report", "--event-log", str(log), "--run-id", "demo")
    (interrupt_report,) = json.loads(out)["runs"][0]["interrupts"]
    assert interrupt_report["status"] == "approved" and interrupt_report["executed"] is True
    assert interrupt_report["decision"]["reason"] == "ok"
    code, out, _ = _cli(capsys, "replay", "--event-log", str(log), "--run-id", "demo", "--format", "text")
    assert f"interrupt id={interrupt_id} tool=checklist step=2" in out
    assert f"approval_decision id={interrupt_id} decision=approved by=alice args_edited=true" in out
    code, out, _ = _cli(capsys, "approvals", "list", "--event-log", str(log), "--all")
    assert "approved" in out and "(edited)" in out


def test_reject_by_run_id_replans(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    log = tmp_path / "runs.sqlite"
    monkeypatch.setenv("MULTIBOT_REQUIRE_APPROVAL", "check*")
    _start(capsys, log, "rej")

    code, out, _ = _cli(capsys, "reject", "--run-id", "rej", "--event-log", str(log), "--reason", "use the template")
    assert code == 0 and json.loads(out)["status"] == "rejected"
    code, out, _ = _cli(capsys, "resume", "--run-id", "rej", "--event-log", str(log))

    assert code == 0
    assert json.loads(out)["answer"] == "re-planned without checklist after a human rejected it (use the template)"
    assert _tool_results(log, "rej") == 0
    code, out, _ = _cli(capsys, "history", "--event-log", str(log), "--run-id", "rej")
    assert "rejected by human" in out and "approval.rejected-needs-replan" in out


def test_fork_honours_and_extends_the_policy(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    log = tmp_path / "runs.sqlite"
    code, _, _ = _cli(capsys, "run", "--goal", GOAL, "--provider", "fake", "--event-log", str(log), "--run-id", "base")
    assert code == 0

    code, out, err = _cli(
        capsys, "fork", "--event-log", str(log), "--run-id", "base", "--at-step", "1", "--new-run-id", "gated",
        "--require-approval", "checklist",
    )  # fmt: skip

    assert code == 3, err
    assert json.loads(out)["interrupt"]["tool"] == "checklist"
    code, out, _ = _cli(capsys, "history", "--event-log", str(log), "--run-id", "gated")
    assert "paused in step 2, awaiting human approval" in out


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (("approve", "int-nope"), "interrupt int-nope not found"),
        (("approve",), "give an interrupt id, or --run-id"),
        (("approve", "--run-id", "demo", "--args", "{not json"), "--args is not valid JSON"),
        (("approve", "--run-id", "demo", "--args", '{"query": "x"}'), "exactly the keys of the requested call"),
        (("approvals", "show", "int-nope"), "interrupt int-nope not found"),
        (("approvals", "list", "--run-id", "ghost"), "run ghost not found"),
    ],
)
def test_decision_errors_are_clean(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, argv: tuple[str, ...], message: str
) -> None:
    log = tmp_path / "runs.sqlite"
    _start(capsys, log, "demo", "--require-approval", "checklist")

    code, _, err = _cli(capsys, *argv, "--event-log", str(log))

    assert code == 2
    assert message in err
    assert "Traceback" not in err


@pytest.mark.parametrize(("value", "kind"), [("null", "null"), ("[]", "array"), ('"text"', "string"), ("7", "number")])
def test_approve_refuses_non_object_args_without_writing(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, value: str, kind: str
) -> None:
    log = tmp_path / "runs.sqlite"
    _start(capsys, log, "demo", "--require-approval", "checklist")

    code, _, err = _cli(capsys, "approve", "--run-id", "demo", "--event-log", str(log), "--args", value)

    assert code == 2
    assert f"--args must be a JSON object, got {kind}" in err
    code, out, _ = _cli(capsys, "approvals", "list", "--event-log", str(log), "--format", "json")
    assert [item["status"] for item in json.loads(out)] == ["pending"]


def test_reject_requires_a_reason(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as raised:
        cli.main(["reject", "int-x", "--event-log", str(tmp_path / "runs.sqlite")])
    assert raised.value.code == 2
    assert "--reason" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("flag", "message"),
    [("chekclist", "matches no registered tool: chekclist"), (" , ", "needs at least one tool name")],
)
def test_bad_policies_are_refused_before_anything_is_written(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, flag: str, message: str
) -> None:
    log = tmp_path / "runs.sqlite"
    code, _, err = _cli(
        capsys, "run", "--goal", GOAL, "--provider", "fake", "--event-log", str(log), "--require-approval", flag
    )

    assert code == 2 and message in err
    assert not log.exists()


def test_read_only_commands_do_not_create_a_missing_log(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    log = tmp_path / "missing.sqlite"
    for argv in (("approvals", "list"), ("approve", "int-x"), ("reject", "int-x", "--reason", "r")):
        code, _, err = _cli(capsys, *argv, "--event-log", str(log))
        assert code == 2 and "event log not found" in err
    assert not log.exists()
