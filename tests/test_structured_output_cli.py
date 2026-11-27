"""End-to-end CLI tests for --output-schema with the fake provider."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from multi_bot_agentic import cli

GOAL = "Plan the agent launch"
SCHEMA = {
    "type": "object",
    "required": ["title", "steps", "risk"],
    "additionalProperties": False,
    "properties": {
        "title": {"type": "string", "minLength": 3},
        "steps": {"type": "array", "items": {"type": "string"}, "minItems": 3},
        "risk": {"enum": ["low", "medium", "high"]},
    },
}


@pytest.fixture(autouse=True)
def _hermetic_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("MULTIBOT_PROVIDER", "MULTIBOT_MAX_STEPS", "MULTIBOT_FAKE_TOOL", "MULTIBOT_REQUIRE_APPROVAL"):
        monkeypatch.delenv(name, raising=False)


def _cli(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, str, str]:
    code = cli.main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def _schema(tmp_path: Path, schema: object = SCHEMA, name: str = "plan.schema.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(schema), encoding="utf-8")
    return path


def _run(capsys: pytest.CaptureFixture[str], log: Path, run_id: str, *extra: str) -> tuple[int, dict[str, object], str]:
    code, out, err = _cli(
        capsys, "run", "--goal", GOAL, "--provider", "fake", "--event-log", str(log), "--run-id", run_id, *extra
    )
    return code, json.loads(out) if out else {}, err


def test_run_validates_after_one_correction_round_and_writes_the_output_file(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    log, output = tmp_path / "runs.sqlite", tmp_path / "out" / "plan.json"
    code, payload, err = _run(
        capsys, log, "demo", "--output-schema", str(_schema(tmp_path)), "--output-file", str(output)
    )

    assert code == 0, err
    assert payload["state"] == "succeeded" and payload["steps"] == 6 and payload["output_attempts"] == 2
    document = payload["output"]
    assert isinstance(document, dict) and document["title"] == GOAL and document["risk"] == "low"
    assert payload["output_file"] == str(output)
    assert json.loads(output.read_text(encoding="utf-8")) == document

    code, out, _ = _cli(capsys, "replay", "--event-log", str(log), "--run-id", "demo", "--format", "text")
    assert code == 0
    assert 'output_validation_failed attempt=1/3 errors=1 retry=true first="$: no JSON document found' in out
    assert "validating final_output attempt=2 source=answer" in out

    code, out, _ = _cli(capsys, "report", "--event-log", str(log), "--run-id", "demo")
    report = json.loads(out)["runs"][0]["output"]
    assert {key: report[key] for key in ("valid", "attempts", "retries")} == {
        "valid": True,
        "attempts": 2,
        "retries": 2,
    }
    assert report["value"] == document and report["schema_source"].endswith("plan.schema.json")

    code, out, _ = _cli(capsys, "history", "--event-log", str(log), "--run-id", "demo")
    assert "output invalid" in out and "output.invalid-needs-correction" in out

    code, out, _ = _cli(capsys, "trace", "--event-log", str(log), "--run-id", "demo", "--format", "mermaid")
    assert "Note over O: output invalid (attempt 1, 1 error)" in out and "Note over O: output valid (attempt 2)" in out
    code, out, _ = _cli(capsys, "trace", "--event-log", str(log), "--run-id", "demo")
    root = json.loads(out)["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
    attributes = {item["key"]: item["value"] for item in root["attributes"]}
    assert attributes["multi_bot_agentic.output.attempts"] == {"intValue": "2"}
    assert attributes["multi_bot_agentic.output.valid"] == {"boolValue": True}
    events = [event["name"] for event in root["events"]]
    assert events.count("multi_bot_agentic.output.validation") == 2


def test_run_without_correction_rounds_exits_4(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    log, output = tmp_path / "runs.sqlite", tmp_path / "plan.json"
    schema = str(_schema(tmp_path))
    code, payload, err = _run(
        capsys, log, "bad", "--output-schema", schema, "--output-retries", "0", "--output-file", str(output)
    )

    assert code == cli.EXIT_OUTPUT_INVALID == 4
    assert payload["state"] == "output_invalid" and payload["steps"] == 4
    assert payload["output_errors"] == [
        "$: no JSON document found; reply with only the JSON document, or put it in one ```json fenced block"
    ]
    assert "output_file" not in payload and not output.exists()
    assert "note: run bad ended in output_invalid" in err

    code, out, err = _cli(capsys, "resume", "--event-log", str(log), "--run-id", "bad")
    assert code == 4 and json.loads(out)["resumed"] is False

    code, out, err = _cli(capsys, "trace", "--event-log", str(log), "--run-id", "bad", "--format", "mermaid")
    assert "Note over O: output_invalid after 4 steps" in out


@pytest.mark.parametrize(
    ("extra", "message"),
    [
        (("--output-file", "out.json"), "error: --output-file needs --output-schema PATH"),
        (("--output-retries", "1"), "error: --output-retries needs --output-schema PATH"),
        (("--output-schema", "missing.json"), "error: cannot read output schema missing.json"),
    ],
)
def test_run_refuses_bad_output_flags(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    extra: tuple[str, ...],
    message: str,
) -> None:
    monkeypatch.chdir(tmp_path)
    code, payload, err = _run(capsys, tmp_path / "runs.sqlite", "r", *extra)
    assert code == 2 and payload == {} and err.startswith(message)
    assert not (tmp_path / "runs.sqlite").exists()


def test_run_refuses_unsupported_schemas_and_directory_outputs(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    unsupported = _schema(tmp_path, {"type": "object", "properties": {"when": {"type": "string", "format": "date"}}})
    code, _, err = _run(capsys, tmp_path / "runs.sqlite", "r", "--output-schema", str(unsupported))
    assert code == 2 and 'schema #/properties/when: unsupported keyword "format"' in err
    code, _, err = _run(
        capsys, tmp_path / "runs.sqlite", "r", "--output-schema", str(_schema(tmp_path)), "--output-file", str(tmp_path)
    )
    assert code == 2 and "is a directory" in err
    with pytest.raises(SystemExit):
        cli.main(["run", "--goal", GOAL, "--output-schema", "s.json", "--output-retries", "11"])


def test_resume_output_file_rewrites_a_finished_runs_output(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    log, output = tmp_path / "runs.sqlite", tmp_path / "again.json"
    code, payload, _ = _run(capsys, log, "demo", "--output-schema", str(_schema(tmp_path)))
    assert code == 0
    code, out, err = _cli(capsys, "resume", "--event-log", str(log), "--run-id", "demo", "--output-file", str(output))
    assert code == 0 and "already finished" in err
    assert json.loads(out)["output_file"] == str(output)
    assert json.loads(output.read_text(encoding="utf-8")) == payload["output"]

    _run(capsys, log, "plain")
    code, _, err = _cli(capsys, "resume", "--event-log", str(log), "--run-id", "plain", "--output-file", str(output))
    assert code == 2 and "run plain has no output schema" in err


def test_fork_with_more_retries_rescues_an_output_invalid_run(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    log = tmp_path / "runs.sqlite"
    schema = str(_schema(tmp_path))
    code, _, _ = _run(capsys, log, "bad", "--output-schema", schema, "--output-retries", "0")
    assert code == 4
    fork = ("fork", "--event-log", str(log), "--run-id", "bad", "--at-step", "3", "--new-run-id", "rescue")
    code, out, _ = _cli(capsys, *fork, "--output-retries", "1", "--dry-run")
    plan = json.loads(out)
    assert code == 0 and plan["overrides"] == {"output_retries": 1} and plan["output_contract"]["retries"] == 1
    code, out, err = _cli(capsys, *fork, "--output-retries", "1", "--output-file", str(tmp_path / "rescued.json"))
    assert code == 0, err
    payload = json.loads(out)
    assert payload["state"] == "succeeded" and payload["output_attempts"] == 2 and payload["parent_run_id"] == "bad"
    assert "new output_retries" in err

    _run(capsys, log, "plain")
    code, _, err = _cli(
        capsys, "fork", "--event-log", str(log), "--run-id", "plain", "--at-step", "1", "--new-run-id", "p2",
        "--output-file", str(tmp_path / "x.json"),
    )  # fmt: skip
    assert code == 2 and "has no output schema, so --output-file needs --output-schema PATH" in err
