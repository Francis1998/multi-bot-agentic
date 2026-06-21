"""Durable sqlite event log for replayable agent runs."""

from __future__ import annotations

import json
import sqlite3
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
        self._connection.commit()
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
