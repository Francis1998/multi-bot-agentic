"""Tests for CLI replay and report formatting helpers."""

from __future__ import annotations

from multi_bot_agentic.cli import build_run_report, format_event, format_event_text
from multi_bot_agentic.event_log import EventRecord


def test_format_event_text_includes_decision_rule() -> None:
    """Text replay output should expose the rationale rule id."""

    event = EventRecord(
        run_id="run-1",
        seq=5,
        timestamp="2026-01-01T00:00:00Z",
        event_type="decision",
        state="deciding",
        payload={
            "action": "call_tool",
            "target": "checklist",
            "rationale": {"rule_id": "model.requested-tool"},
        },
    )

    assert format_event_text(event) == "005 deciding   decision action=call_tool rule=model.requested-tool"


def test_format_event_json_includes_payload() -> None:
    """JSON replay output should remain machine-readable."""

    event = EventRecord(
        run_id="run-1",
        seq=1,
        timestamp="2026-01-01T00:00:00Z",
        event_type="run_created",
        state="created",
        payload={"goal": "demo"},
    )

    assert '"event_type": "run_created"' in format_event(event, "json")
    assert '"goal": "demo"' in format_event(event, "json")


def test_build_run_report_summarizes_decisions_tools_and_answer() -> None:
    """Reports should summarize final state, decisions, tools, and answer."""

    events = [
        EventRecord("run-1", 1, "ts", "run_created", "created", {"goal": "demo"}),
        EventRecord(
            "run-1",
            2,
            "ts",
            "decision",
            "deciding",
            {
                "action": "call_tool",
                "target": "checklist",
                "rationale": {"rule_id": "model.requested-tool"},
            },
        ),
        EventRecord(
            "run-1",
            3,
            "ts",
            "action_result",
            "acting",
            {"kind": "tool", "tool": "checklist", "ok": True},
        ),
        EventRecord("run-1", 4, "ts", "run_completed", "succeeded", {"answer": "done"}),
    ]

    report = build_run_report(events)

    assert report["runs"][0]["final_state"] == "succeeded"
    assert report["runs"][0]["decisions"][0]["rule_id"] == "model.requested-tool"
    assert report["runs"][0]["tool_calls"][0]["tool"] == "checklist"
    assert report["runs"][0]["answer"] == "done"
