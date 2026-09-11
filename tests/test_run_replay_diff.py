"""Tests for RunReplayDiff."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from multi_bot_agentic.run_replay_diff import RunReplayDiff


def test_equal_ignoring_timestamps() -> None:
    """Identical event_type/state/payload are equal even when timestamps differ."""

    left = [
        {
            "event_type": "decision",
            "state": "decide",
            "timestamp": "2026-01-01T00:00:00Z",
            "payload": {"tool": "echo", "created_at": "t1"},
        }
    ]
    right = [
        {
            "event_type": "decision",
            "state": "decide",
            "timestamp": "2026-09-11T12:00:00Z",
            "payload": {"tool": "echo", "created_at": "t2"},
        }
    ]
    result = RunReplayDiff().diff(left, right)
    assert result.equal is True
    assert result.left_count == 1
    assert result.right_count == 1
    assert result.added_indices == ()
    assert result.removed_indices == ()
    assert result.changed_indices == ()
    assert result.entries == ()


def test_changed_payload() -> None:
    """Payload drift is reported as changed."""

    left = [{"event_type": "act", "state": "act", "payload": {"tool": "a"}}]
    right = [{"event_type": "act", "state": "act", "payload": {"tool": "b"}}]
    result = RunReplayDiff().diff(left, right)
    assert result.equal is False
    assert result.changed_indices == (0,)
    assert result.entries[0].kind == "changed"
    assert result.entries[0].left is not None
    assert result.entries[0].right is not None
    assert result.entries[0].left["payload"]["tool"] == "a"
    assert result.entries[0].right["payload"]["tool"] == "b"


def test_added_and_removed() -> None:
    """Length mismatches yield added/removed indices."""

    left = [
        {"event_type": "observe", "state": "observe", "payload": {}},
        {"event_type": "decide", "state": "decide", "payload": {"n": 1}},
    ]
    right = [
        {"event_type": "observe", "state": "observe", "payload": {}},
    ]
    result = RunReplayDiff().diff(left, right)
    assert result.removed_indices == (1,)
    assert result.added_indices == ()
    assert result.entries[0].kind == "removed"

    longer_right = RunReplayDiff().diff(right, left)
    assert longer_right.added_indices == (1,)
    assert longer_right.removed_indices == ()
    assert longer_right.entries[0].kind == "added"


def test_event_record_like() -> None:
    """Objects with event_type/state/payload attributes are accepted."""

    @dataclass(frozen=True)
    class FakeRecord:
        event_type: str
        state: str
        payload: dict[str, Any]
        timestamp: str

    left = [FakeRecord("decision", "decide", {"ok": True, "ts": "old"}, "t-left")]
    right = [FakeRecord("decision", "decide", {"ok": True, "ts": "new"}, "t-right")]
    result = RunReplayDiff().diff(left, right)
    assert result.equal is True


def test_rejects_non_sequence() -> None:
    """Non-sequence inputs raise TypeError."""

    with pytest.raises(TypeError, match="left_events"):
        RunReplayDiff().diff({"event_type": "x"}, [])  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="right_events"):
        RunReplayDiff().diff([], "nope")


def test_rejects_bad_event_item() -> None:
    """Non-mapping event items raise TypeError."""

    with pytest.raises(TypeError, match="left\\[0\\]"):
        RunReplayDiff().diff([42], [])
