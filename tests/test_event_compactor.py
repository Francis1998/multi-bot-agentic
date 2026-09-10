"""Tests for EventLogCompactor."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from multi_bot_agentic.event_compactor import EventLogCompactor


def test_invalid_keep_raises() -> None:
    """keep_head < 1 raises ValueError."""

    with pytest.raises(ValueError, match="keep_head"):
        EventLogCompactor(keep_head=0)


def test_compact_noop_when_small() -> None:
    """Lists within the window are unchanged."""

    events = [{"seq": i} for i in range(3)]
    result = EventLogCompactor(keep_head=2, keep_tail=2).compact(events)
    assert result.dropped_count == 0
    assert result.events == events


def test_compact_drops_middle() -> None:
    """Large lists keep head + marker + tail."""

    events = [{"seq": i} for i in range(10)]
    result = EventLogCompactor(keep_head=2, keep_tail=2).compact(events)
    assert result.original_count == 10
    assert result.dropped_count == 6
    assert result.events[0] == {"seq": 0}
    assert result.events[1] == {"seq": 1}
    assert result.events[2]["event_type"] == "event_log.compacted"
    assert result.events[-2] == {"seq": 8}
    assert result.events[-1] == {"seq": 9}


def test_compact_jsonl(tmp_path: Path) -> None:
    """JSONL files are rewritten with compacted events."""

    path = tmp_path / "events.jsonl"
    path.write_text("".join(json.dumps({"seq": i}) + "\n" for i in range(8)), encoding="utf-8")
    result = EventLogCompactor(keep_head=1, keep_tail=1).compact_jsonl(path)
    assert result.dropped_count == 6
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert json.loads(lines[0]) == {"seq": 0}
    assert json.loads(lines[1])["event_type"] == "event_log.compacted"
    assert json.loads(lines[2]) == {"seq": 7}


def test_compact_rejects_non_list() -> None:
    """Non-list input raises TypeError."""

    with pytest.raises(TypeError, match="list"):
        EventLogCompactor().compact({"seq": 1})  # type: ignore[arg-type]
