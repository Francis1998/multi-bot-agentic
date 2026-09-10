"""Bounded JSONL / event-list compaction for long multi-bot runs.

Keeps head + tail events and drops the middle when logs exceed a max size.
Distinct from LangSmith / Langfuse retention policies — this is a thin,
stdlib-only offline compactor suitable for GPT-5.5 / Claude Sonnet 4.6 /
Gemini 3.x / Kimi K2 ODA event streams.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CompactionResult:
    """Result of compacting an event list.

    Attributes:
        events: Compacted event dictionaries.
        original_count: Input event count.
        dropped_count: Number of middle events removed.
    """

    events: list[dict[str, Any]]
    original_count: int
    dropped_count: int


class EventLogCompactor:
    """Compact event lists / JSONL files by retaining head and tail windows."""

    def __init__(self, *, keep_head: int = 50, keep_tail: int = 50) -> None:
        if keep_head < 1:
            raise ValueError("keep_head must be >= 1")
        if keep_tail < 1:
            raise ValueError("keep_tail must be >= 1")
        self._keep_head = keep_head
        self._keep_tail = keep_tail

    @property
    def keep_head(self) -> int:
        """Return configured keep_head."""

        return self._keep_head

    @property
    def keep_tail(self) -> int:
        """Return configured keep_tail."""

        return self._keep_tail

    def compact(self, events: list[dict[str, Any]]) -> CompactionResult:
        """Compact an in-memory event list.

        Args:
            events: Ordered event dictionaries.

        Returns:
            CompactionResult with possibly truncated events.

        Raises:
            TypeError: When events is not a list.
        """

        if not isinstance(events, list):
            raise TypeError("events must be a list")

        original = len(events)
        window = self._keep_head + self._keep_tail
        if original <= window:
            return CompactionResult(
                events=list(events),
                original_count=original,
                dropped_count=0,
            )

        head = events[: self._keep_head]
        tail = events[-self._keep_tail :]
        marker = {
            "event_type": "event_log.compacted",
            "dropped_count": original - window,
            "keep_head": self._keep_head,
            "keep_tail": self._keep_tail,
        }
        compacted = [*head, marker, *tail]
        return CompactionResult(
            events=compacted,
            original_count=original,
            dropped_count=original - window,
        )

    def compact_jsonl(self, path: Path, *, output: Path | None = None) -> CompactionResult:
        """Compact a JSONL event file.

        Args:
            path: Source JSONL path (one JSON object per line).
            output: Optional destination path (defaults to overwrite ``path``).

        Returns:
            CompactionResult for the compacted events.

        Raises:
            FileNotFoundError: When path does not exist.
            ValueError: When a line is not a JSON object.
        """

        if not path.is_file():
            raise FileNotFoundError(f"event log not found: {path}")

        events: list[dict[str, Any]] = []
        for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            text = raw.strip()
            if not text:
                continue
            parsed = json.loads(text)
            if not isinstance(parsed, dict):
                raise ValueError(f"line {line_no} must be a JSON object")
            events.append(parsed)

        result = self.compact(events)
        dest = output if output is not None else path
        dest.write_text(
            "".join(json.dumps(event, ensure_ascii=True) + "\n" for event in result.events),
            encoding="utf-8",
        )
        return result
