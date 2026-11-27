"""Durable sqlite event log for replayable agent runs."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from multi_bot_agentic.models import EventType, RunState

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS events (
  run_id TEXT NOT NULL,
  seq INTEGER NOT NULL,
  timestamp TEXT NOT NULL,
  event_type TEXT NOT NULL,
  state TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  PRIMARY KEY (run_id, seq)
);

CREATE INDEX IF NOT EXISTS idx_events_run_id_seq ON events (run_id, seq);
"""


@dataclass(frozen=True)
class EventRecord:
    """One durable event-log entry."""

    run_id: str
    seq: int
    timestamp: str
    event_type: str
    state: str
    payload: dict[str, Any]


class SQLiteEventLog:
    """Append-only sqlite event log with per-run monotonic sequence numbers."""

    def __init__(self, path: Path) -> None:
        """Initialize the event log.

        Args:
            path: Path to sqlite database.
        """

        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._connection = sqlite3.connect(path)
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.executescript(SCHEMA_SQL)
        self._connection.commit()

    def append(
        self,
        run_id: str,
        state: RunState,
        event_type: EventType,
        payload: dict[str, Any],
    ) -> EventRecord:
        """Append one event and return the persisted record.

        Args:
            run_id: Run identifier.
            state: State at event time.
            event_type: Event category.
            payload: JSON-serializable payload.

        Returns:
            Persisted event record.
        """

        record = self._insert(run_id, state, event_type, payload)
        self._connection.commit()
        return record

    def append_guarded(
        self,
        run_id: str,
        entries: Sequence[tuple[RunState, EventType, dict[str, Any]]],
        guard: Callable[[list[EventRecord]], None] | None = None,
    ) -> list[EventRecord]:
        """Atomically check a run's events and append events, or append nothing.

        The check and the inserts run in one ``BEGIN IMMEDIATE`` transaction, which holds
        SQLite's write lock, so two processes cannot both pass the same check (for example two
        decisions on one interrupt, or two resumes executing one approved tool call). Without a
        guard the events are still all-or-nothing: a process that dies midway leaves none of them.

        Args:
            run_id: Run identifier.
            entries: ``(state, event_type, payload)`` of each event to append, in order.
            guard: Called with the run's events; raises to abort without appending. ``None`` skips
                the check.

        Returns:
            The persisted records.
        """

        if self._connection.in_transaction:
            self._connection.commit()
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            if guard is not None:
                guard(self.list_events(run_id))
            records = [self._insert(run_id, state, event_type, payload) for state, event_type, payload in entries]
        except BaseException:
            self._connection.rollback()
            raise
        self._connection.commit()
        return records

    def _insert(self, run_id: str, state: RunState, event_type: EventType, payload: dict[str, Any]) -> EventRecord:
        """Insert one event without committing."""

        seq = self._next_sequence(run_id)
        timestamp = datetime.now(timezone.utc).isoformat()
        payload_json = json.dumps(payload, sort_keys=True)
        self._connection.execute(
            """
            INSERT INTO events (run_id, seq, timestamp, event_type, state, payload_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (run_id, seq, timestamp, event_type.value, state.value, payload_json),
        )
        return EventRecord(
            run_id=run_id,
            seq=seq,
            timestamp=timestamp,
            event_type=event_type.value,
            state=state.value,
            payload=payload,
        )

    def list_events(self, run_id: str | None = None) -> list[EventRecord]:
        """List events ordered by run and sequence.

        Args:
            run_id: Optional run identifier filter.

        Returns:
            Ordered event records.
        """

        if run_id is None:
            cursor = self._connection.execute(
                "SELECT run_id, seq, timestamp, event_type, state, payload_json FROM events ORDER BY run_id, seq"
            )
        else:
            cursor = self._connection.execute(
                "SELECT run_id, seq, timestamp, event_type, state, payload_json FROM events "
                "WHERE run_id = ? ORDER BY seq",
                (run_id,),
            )
        return [
            EventRecord(
                run_id=row[0],
                seq=row[1],
                timestamp=row[2],
                event_type=row[3],
                state=row[4],
                payload=json.loads(row[5]),
            )
            for row in cursor.fetchall()
        ]

    def close(self) -> None:
        """Close the sqlite connection."""

        self._connection.close()

    def last_event_timestamps(self) -> dict[str, str]:
        """Return each run's latest event timestamp (the event with the highest sequence number).

        Returns:
            Timestamps keyed by run id; empty when the log has no events.
        """

        cursor = self._connection.execute(
            "SELECT events.run_id, events.timestamp FROM events "
            "JOIN (SELECT run_id, MAX(seq) AS seq FROM events GROUP BY run_id) AS latest "
            "ON events.run_id = latest.run_id AND events.seq = latest.seq"
        )
        return {str(row[0]): str(row[1]) for row in cursor.fetchall()}

    def _next_sequence(self, run_id: str) -> int:
        """Return the next sequence number for a run.

        Args:
            run_id: Run identifier.

        Returns:
            Next event sequence number.
        """

        row = self._connection.execute(
            "SELECT COALESCE(MAX(seq), 0) + 1 FROM events WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        return int(row[0])
