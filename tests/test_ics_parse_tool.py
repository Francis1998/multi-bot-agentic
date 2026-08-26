"""Tests for the iCalendar VEVENT parse tool."""

from __future__ import annotations

import json
from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.ics_parse import IcsParseTool

_SAMPLE = (
    "BEGIN:VCALENDAR\r\n"
    "VERSION:2.0\r\n"
    "BEGIN:VEVENT\r\n"
    "UID:gpt-55@example.com\r\n"
    "SUMMARY:GPT-5.5 sync\r\n"
    "DTSTART:20260826T160000Z\r\n"
    "DTEND:20260826T170000Z\r\n"
    "LOCATION:Room A\r\n"
    "END:VEVENT\r\n"
    "BEGIN:VEVENT\r\n"
    "UID:claude-46@example.com\r\n"
    "SUMMARY:Claude Sonnet 4.6 review\r\n"
    "DTSTART:20260827T090000Z\r\n"
    "DTEND:20260827T100000Z\r\n"
    "LOCATION:Gemini 3.x lab\r\n"
    "END:VEVENT\r\n"
    "END:VCALENDAR\r\n"
)


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the ics_parse tool."""

    result = IcsParseTool().execute(ToolInvocation(tool_name="ics_parse", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_ics_parse_extracts_vevent_fields() -> None:
    """VEVENT SUMMARY/DTSTART/DTEND/UID/LOCATION become JSON Lines."""

    ok, content, metadata = _run(text=_SAMPLE)

    assert ok is True
    lines = [line for line in content.splitlines() if line]
    assert len(lines) == 2
    first = json.loads(lines[0])
    second = json.loads(lines[1])
    assert first["SUMMARY"] == "GPT-5.5 sync"
    assert first["UID"] == "gpt-55@example.com"
    assert first["DTSTART"] == "20260826T160000Z"
    assert first["DTEND"] == "20260826T170000Z"
    assert first["LOCATION"] == "Room A"
    assert second["SUMMARY"] == "Claude Sonnet 4.6 review"
    assert second["LOCATION"] == "Gemini 3.x lab"
    assert metadata["events"] == 2


def test_ics_parse_unfolds_folded_lines_and_unescapes() -> None:
    """Folded SUMMARY lines and TEXT escapes are restored."""

    document = (
        "BEGIN:VEVENT\n"
        "UID:kimi-k2\n"
        "SUMMARY:Kimi K2 plan\\, part 1\n"
        " DTSTART note\n"
        "DTSTART:20260101T120000Z\n"
        "DTEND:20260101T130000Z\n"
        "LOCATION:HQ\\; desk\n"
        "END:VEVENT\n"
    )
    ok, content, metadata = _run(text=document)

    assert ok is True
    event = json.loads(content.splitlines()[0])
    assert event["SUMMARY"] == "Kimi K2 plan, part 1DTSTART note"
    assert event["LOCATION"] == "HQ; desk"
    assert metadata["events"] == 1


def test_ics_parse_rejects_empty_oversized_and_missing_events() -> None:
    """Empty, oversized, and VEVENT-less inputs fail."""

    ok_empty, content_empty, _m1 = _run(text="   ")
    ok_big, content_big, meta = _run(text="x" * 20_001)
    ok_none, content_none, _m3 = _run(text="BEGIN:VCALENDAR\nEND:VCALENDAR\n")

    assert ok_empty is False and "empty" in content_empty
    assert ok_big is False and "max_chars" in content_big and meta["chars"] == 20_001
    assert ok_none is False and "no VEVENT" in content_none


def test_ics_parse_rejects_too_many_events() -> None:
    """More than 100 VEVENT blocks fail the event cap."""

    body = "".join(
        (
            "BEGIN:VEVENT\n"
            f"UID:e{index}\n"
            f"SUMMARY:Event {index}\n"
            "DTSTART:20260101T000000Z\n"
            "DTEND:20260101T010000Z\n"
            "END:VEVENT\n"
        )
        for index in range(101)
    )
    ok, content, metadata = _run(text=body)

    assert ok is False
    assert "max_events=100" in content
    assert metadata["events"] == 101


def test_ics_parse_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "ics_parse" in tools
    assert tools["ics_parse"].name == "ics_parse"
    SafetyPolicy().validate_tool("ics_parse")
    assert "ics_parse" in SafetyPolicy().allowed_tools
