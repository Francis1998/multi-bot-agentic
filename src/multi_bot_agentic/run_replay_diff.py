"""Run-to-run event-log replay diff for multi-bot agent loops.

Compare two event sequences for drift on ``event_type`` / ``state`` /
normalized ``payload`` while ignoring timestamp fields. Distinct from
``EventLogCompactor`` (size compaction) — this is a thin, stdlib-only
drift checker suitable for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x /
Kimi K2 ODA runs. Fills a gap vs AutoGen/CrewAI, which often lack
run-to-run drift diffs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final, Mapping, Sequence

_TIMESTAMP_KEYS: Final[frozenset[str]] = frozenset(
    {
        "timestamp",
        "ts",
        "time",
        "datetime",
        "created_at",
        "updated_at",
        "recorded_at",
    }
)


@dataclass(frozen=True)
class DiffEntry:
    """One positional drift between left and right runs.

    Attributes:
        index: Zero-based event index in the longer alignment.
        kind: ``added`` (right-only), ``removed`` (left-only), or ``changed``.
        left: Normalized left event at ``index``, or ``None`` when added.
        right: Normalized right event at ``index``, or ``None`` when removed.
    """

    index: int
    kind: str
    left: dict[str, Any] | None
    right: dict[str, Any] | None


@dataclass(frozen=True)
class ReplayDiffResult:
    """Outcome of comparing two event-log run sequences.

    Attributes:
        equal: True when sequences match ignoring timestamps.
        left_count: Number of left events.
        right_count: Number of right events.
        added_indices: Indices present only on the right.
        removed_indices: Indices present only on the left.
        changed_indices: Indices present on both sides but differing.
        entries: Ordered drift entries (added / removed / changed).
    """

    equal: bool
    left_count: int
    right_count: int
    added_indices: tuple[int, ...]
    removed_indices: tuple[int, ...]
    changed_indices: tuple[int, ...]
    entries: tuple[DiffEntry, ...]


class RunReplayDiff:
    """Diff two event-log runs for drift, ignoring timestamps.

    Caller-driven v1: pass event mappings (or EventRecord-like objects) from
    two runs. Does not wire into the runner automatically.
    """

    def diff(
        self,
        left_events: Sequence[Mapping[str, Any] | Any],
        right_events: Sequence[Mapping[str, Any] | Any],
    ) -> ReplayDiffResult:
        """Compare ``left_events`` to ``right_events``.

        Events are compared by position on ``event_type``, ``state``, and a
        payload with timestamp-like keys stripped. Top-level ``timestamp``
        (and similar) fields are ignored.

        Args:
            left_events: Baseline run event sequence.
            right_events: Comparison run event sequence.

        Returns:
            ReplayDiffResult with equality flag and drift indices.

        Raises:
            TypeError: When either side is not a sequence, or an item is not
                a mapping / EventRecord-like object.
        """

        left_list = _coerce_sequence(left_events, side="left_events")
        right_list = _coerce_sequence(right_events, side="right_events")

        left_norm = [_normalize_event(event, index=i, side="left") for i, event in enumerate(left_list)]
        right_norm = [_normalize_event(event, index=i, side="right") for i, event in enumerate(right_list)]

        entries: list[DiffEntry] = []
        added: list[int] = []
        removed: list[int] = []
        changed: list[int] = []

        shared = min(len(left_norm), len(right_norm))
        for index in range(shared):
            if left_norm[index] != right_norm[index]:
                changed.append(index)
                entries.append(
                    DiffEntry(
                        index=index,
                        kind="changed",
                        left=left_norm[index],
                        right=right_norm[index],
                    )
                )

        for index in range(shared, len(left_norm)):
            removed.append(index)
            entries.append(
                DiffEntry(
                    index=index,
                    kind="removed",
                    left=left_norm[index],
                    right=None,
                )
            )

        for index in range(shared, len(right_norm)):
            added.append(index)
            entries.append(
                DiffEntry(
                    index=index,
                    kind="added",
                    left=None,
                    right=right_norm[index],
                )
            )

        return ReplayDiffResult(
            equal=not entries,
            left_count=len(left_norm),
            right_count=len(right_norm),
            added_indices=tuple(added),
            removed_indices=tuple(removed),
            changed_indices=tuple(changed),
            entries=tuple(entries),
        )


def _coerce_sequence(events: Sequence[Mapping[str, Any] | Any], *, side: str) -> list[Any]:
    if isinstance(events, (str, bytes)) or not isinstance(events, Sequence):
        raise TypeError(f"{side} must be a sequence of event mappings")
    return list(events)


def _normalize_event(event: Mapping[str, Any] | Any, *, index: int, side: str) -> dict[str, Any]:
    mapping = _as_mapping(event, index=index, side=side)
    event_type = mapping.get("event_type", "")
    state = mapping.get("state", "")
    payload = mapping.get("payload", {})
    if payload is None:
        payload = {}
    if not isinstance(payload, Mapping):
        raise TypeError(f"{side}[{index}].payload must be a mapping")
    return {
        "event_type": str(event_type),
        "state": str(state),
        "payload": _strip_timestamps(payload),
    }


def _as_mapping(event: Mapping[str, Any] | Any, *, index: int, side: str) -> Mapping[str, Any]:
    if isinstance(event, Mapping):
        return event
    # EventRecord-like: expose event_type / state / payload attributes.
    if all(hasattr(event, attr) for attr in ("event_type", "state", "payload")):
        return {
            "event_type": getattr(event, "event_type"),
            "state": getattr(event, "state"),
            "payload": getattr(event, "payload"),
            "timestamp": getattr(event, "timestamp", None),
        }
    raise TypeError(f"{side}[{index}] must be a mapping or EventRecord-like object")


def _strip_timestamps(value: Any) -> Any:
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if str(key).casefold() in _TIMESTAMP_KEYS:
                continue
            out[str(key)] = _strip_timestamps(item)
        return out
    if isinstance(value, list):
        return [_strip_timestamps(item) for item in value]
    if isinstance(value, tuple):
        return [_strip_timestamps(item) for item in value]
    return value
