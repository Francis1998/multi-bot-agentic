"""In-process shared blackboard for multi-bot coordination.

Bots can publish short string facts under stable keys so later steps (or sibling
bots) can read them without threading payloads through every observation.

This is intentionally thinner than CrewAI/AutoGen shared memory stores or
LangGraph shared state channels: no persistence, no embeddings, no graph
channels — just bounded key/value entries with revision counters suitable for
GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 multi-bot loops.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BlackboardEntry:
    """One published blackboard value.

    Attributes:
        key: Stable lookup key.
        value: Opaque UTF-8 text payload.
        writer_bot_id: Optional bot that wrote the entry.
        revision: Monotonic revision for this key (starts at 1).
    """

    key: str
    value: str
    writer_bot_id: str | None
    revision: int


class SharedBlackboard:
    """Bounded in-memory key/value board for multi-bot handoffs.

    Args:
        max_keys: Maximum distinct keys allowed at once.
        max_value_chars: Maximum characters permitted per value.
    """

    def __init__(self, *, max_keys: int = 64, max_value_chars: int = 4000) -> None:
        if max_keys < 1:
            raise ValueError("max_keys must be >= 1")
        if max_value_chars < 1:
            raise ValueError("max_value_chars must be >= 1")
        self._max_keys = max_keys
        self._max_value_chars = max_value_chars
        self._entries: dict[str, BlackboardEntry] = {}

    def put(self, key: str, value: str, *, writer_bot_id: str | None = None) -> BlackboardEntry:
        """Insert or replace a blackboard entry.

        Args:
            key: Non-empty lookup key.
            value: Text payload (bounded by ``max_value_chars``).
            writer_bot_id: Optional bot identifier for audit.

        Returns:
            The stored entry (with incremented revision on overwrite).

        Raises:
            ValueError: Empty key, oversize value, or max_keys exceeded for a new key.
        """

        normalized_key = key.strip()
        if not normalized_key:
            raise ValueError("key must be non-empty")
        if len(value) > self._max_value_chars:
            raise ValueError(f"value exceeds max_value_chars ({self._max_value_chars})")
        existing = self._entries.get(normalized_key)
        if existing is None and len(self._entries) >= self._max_keys:
            raise ValueError(f"max_keys exceeded ({self._max_keys})")
        revision = 1 if existing is None else existing.revision + 1
        entry = BlackboardEntry(
            key=normalized_key,
            value=value,
            writer_bot_id=writer_bot_id,
            revision=revision,
        )
        self._entries[normalized_key] = entry
        return entry

    def get(self, key: str) -> BlackboardEntry | None:
        """Return the entry for ``key``, or ``None`` when missing.

        Args:
            key: Lookup key (leading/trailing whitespace ignored).

        Returns:
            Stored entry or ``None``.
        """

        return self._entries.get(key.strip())

    def delete(self, key: str) -> bool:
        """Delete an entry by key.

        Args:
            key: Lookup key.

        Returns:
            ``True`` when an entry was removed, otherwise ``False``.
        """

        normalized_key = key.strip()
        if normalized_key not in self._entries:
            return False
        del self._entries[normalized_key]
        return True

    def snapshot(self) -> dict[str, BlackboardEntry]:
        """Return a shallow copy of all current entries.

        Returns:
            Mapping of key → entry (safe to mutate independently).
        """

        return dict(self._entries)
