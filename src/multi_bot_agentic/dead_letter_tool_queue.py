"""Dead-letter queue for permanently failed tool calls (HITL replay).

Captures exhausted tool failures after retries/circuit breakers give up so an
operator can inspect and acknowledge them. Distinct from
``ToolRetryBackoffPolicy`` (transient retries) and ``ToolCircuitBreaker``
(fail-fast open circuits) — this is a post-exhaustion HITL queue for
GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 tool loops. Fills a gap
vs AutoGen/CrewAI/LangGraph, which often drop failed tool payloads after
retry exhaustion.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class DeadLetterItem:
    """One permanently failed tool call awaiting HITL review.

    Attributes:
        item_id: Stable unique identifier.
        tool_name: Tool that failed.
        args: Shallow copy of tool arguments at enqueue time.
        error: Error message / reason for permanent failure.
        attempt_count: How many attempts were made before enqueue.
        enqueued_at_iso: UTC ISO-8601 timestamp when enqueued.
        acknowledged: Whether an operator has acknowledged the item.
    """

    item_id: str
    tool_name: str
    args: Mapping[str, Any]
    error: str
    attempt_count: int
    enqueued_at_iso: str
    acknowledged: bool = False


class DeadLetterToolQueue:
    """In-memory dead-letter queue for exhausted tool failures.

    Caller-driven v1: enqueue after retries/circuit breakers exhaust; list
    pending items for HITL; acknowledge once handled. Never performs network I/O.
    """

    def __init__(self) -> None:
        self._items: dict[str, DeadLetterItem] = {}

    def enqueue(
        self,
        tool_name: str,
        args: Mapping[str, Any],
        error: str,
        attempt_count: int,
        *,
        enqueued_at_iso: str | None = None,
    ) -> DeadLetterItem:
        """Enqueue a permanently failed tool call.

        Args:
            tool_name: Failed tool name (non-empty).
            args: Tool arguments mapping (copied).
            error: Failure reason (non-empty).
            attempt_count: Attempts made before permanent failure (>= 1).
            enqueued_at_iso: Optional UTC ISO timestamp; defaults to now.

        Returns:
            Newly enqueued DeadLetterItem (pending).

        Raises:
            ValueError: When required fields are invalid.
            TypeError: When ``args`` is not a mapping.
        """

        if not tool_name.strip():
            raise ValueError("tool_name must be non-empty")
        if not isinstance(args, Mapping):
            raise TypeError("args must be a mapping")
        if not error.strip():
            raise ValueError("error must be non-empty")
        if attempt_count < 1:
            raise ValueError("attempt_count must be >= 1")

        item = DeadLetterItem(
            item_id=str(uuid4()),
            tool_name=tool_name.strip(),
            args=dict(args),
            error=error.strip(),
            attempt_count=attempt_count,
            enqueued_at_iso=enqueued_at_iso or datetime.now(timezone.utc).isoformat(),
            acknowledged=False,
        )
        self._items[item.item_id] = item
        return item

    def list_pending(self) -> list[DeadLetterItem]:
        """Return unacknowledged items in enqueue order.

        Returns:
            Pending DeadLetterItem list.
        """

        return [item for item in self._items.values() if not item.acknowledged]

    def acknowledge(self, item_id: str) -> DeadLetterItem:
        """Mark a dead-letter item as acknowledged (HITL handled).

        Args:
            item_id: Identifier returned from ``enqueue``.

        Returns:
            Updated DeadLetterItem with ``acknowledged=True``.

        Raises:
            KeyError: When ``item_id`` is unknown.
            ValueError: When ``item_id`` is empty or already acknowledged.
        """

        if not item_id.strip():
            raise ValueError("item_id must be non-empty")
        existing = self._items.get(item_id)
        if existing is None:
            raise KeyError(f"unknown dead-letter item: {item_id}")
        if existing.acknowledged:
            raise ValueError(f"item already acknowledged: {item_id}")
        updated = DeadLetterItem(
            item_id=existing.item_id,
            tool_name=existing.tool_name,
            args=existing.args,
            error=existing.error,
            attempt_count=existing.attempt_count,
            enqueued_at_iso=existing.enqueued_at_iso,
            acknowledged=True,
        )
        self._items[item_id] = updated
        return updated
