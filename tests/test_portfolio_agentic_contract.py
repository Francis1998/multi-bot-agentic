"""Portfolio: event log durability contract."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.event_log import SQLiteEventLog
from multi_bot_agentic.models import EventType, RunState


def test_event_log_append_list_roundtrip(tmp_path: Path) -> None:
    """Events append with monotonic seq and list by run_id."""
    log = SQLiteEventLog(tmp_path / "events.sqlite3")
    log.append("run-1", RunState.OBSERVING, EventType.OBSERVATION, {"step": 1})
    log.append("run-1", RunState.DECIDING, EventType.DECISION, {"step": 2})
    events = log.list_events("run-1")
    assert len(events) == 2
    assert events[0].seq == 1
    assert events[1].payload["step"] == 2
    log.close()
