"""Tests for durable sqlite event logging."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.event_log import SQLiteEventLog
from multi_bot_agentic.models import EventType, RunState


def test_event_log_persists_monotonic_sequences(tmp_path: Path) -> None:
    """Events are persisted with per-run monotonic sequence numbers."""

    log = SQLiteEventLog(tmp_path / "runs.sqlite")
    try:
        log.append("run-1", RunState.CREATED, EventType.RUN_CREATED, {"goal": "test"})
        log.append("run-1", RunState.OBSERVING, EventType.OBSERVATION, {"source": "user"})
        events = log.list_events("run-1")
    finally:
        log.close()

    assert [event.seq for event in events] == [1, 2]
    assert events[0].payload == {"goal": "test"}
