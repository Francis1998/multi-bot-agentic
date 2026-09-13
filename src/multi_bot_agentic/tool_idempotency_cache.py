"""Idempotent tool-call result cache for retry-safe replay.

Caches tool results by a stable hash of ``tool_name`` plus canonical args so
retries can replay without re-executing. Distinct from
``DeadLetterToolQueue`` (post-exhaustion HITL) and ``ToolResultTruncator``
(payload size capping) — this is a thin, stdlib-only idempotency cache for
GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 tool loops. Fills a gap
vs AutoGen/CrewAI/LangGraph, which often re-run identical tool calls on
retry.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class ToolCacheEntry:
    """Immutable cached tool result.

    Attributes:
        cache_key: Stable hash of tool name + canonical args.
        tool_name: Tool that produced the result.
        args: Shallow copy of tool arguments at put time.
        result: Cached tool result payload (opaque).
        cached_at_iso: UTC ISO-8601 timestamp when cached.
    """

    cache_key: str
    tool_name: str
    args: Mapping[str, Any]
    result: Any
    cached_at_iso: str


class ToolCallIdempotencyCache:
    """In-memory idempotency cache for identical tool calls.

    Caller-driven v1: ``put`` after a successful tool execute; ``get`` before
    retry to replay; ``invalidate`` when a result must be refreshed. Never
    performs network I/O.
    """

    def __init__(self) -> None:
        self._entries: dict[str, ToolCacheEntry] = {}

    @staticmethod
    def make_key(tool_name: str, args: Mapping[str, Any]) -> str:
        """Build a stable cache key from tool name and canonical args.

        Args:
            tool_name: Tool name (already validated / stripped).
            args: Mapping of tool arguments.

        Returns:
            Hex SHA-256 digest string.
        """

        canonical = json.dumps(args, sort_keys=True, default=str, separators=(",", ":"))
        payload = f"{tool_name}\0{canonical}".encode()
        return hashlib.sha256(payload).hexdigest()

    def put(
        self,
        tool_name: str,
        args: Mapping[str, Any],
        result: Any,
        *,
        cached_at_iso: str | None = None,
    ) -> ToolCacheEntry:
        """Store a tool result under the idempotency key.

        Args:
            tool_name: Tool name (non-empty).
            args: Tool arguments mapping (copied).
            result: Opaque result to cache.
            cached_at_iso: Optional UTC ISO timestamp; defaults to now.

        Returns:
            Newly stored ToolCacheEntry.

        Raises:
            ValueError: When ``tool_name`` is empty.
            TypeError: When ``args`` is not a mapping.
        """

        if not tool_name.strip():
            raise ValueError("tool_name must be non-empty")
        if not isinstance(args, Mapping):
            raise TypeError("args must be a mapping")

        name = tool_name.strip()
        copied = dict(args)
        key = self.make_key(name, copied)
        entry = ToolCacheEntry(
            cache_key=key,
            tool_name=name,
            args=copied,
            result=result,
            cached_at_iso=cached_at_iso or datetime.now(timezone.utc).isoformat(),
        )
        self._entries[key] = entry
        return entry

    def get(self, tool_name: str, args: Mapping[str, Any]) -> ToolCacheEntry | None:
        """Return a cached entry for tool+args, or None on miss.

        Args:
            tool_name: Tool name (non-empty).
            args: Tool arguments mapping.

        Returns:
            Matching ToolCacheEntry or None.

        Raises:
            ValueError: When ``tool_name`` is empty.
            TypeError: When ``args`` is not a mapping.
        """

        if not tool_name.strip():
            raise ValueError("tool_name must be non-empty")
        if not isinstance(args, Mapping):
            raise TypeError("args must be a mapping")
        key = self.make_key(tool_name.strip(), dict(args))
        return self._entries.get(key)

    def invalidate(self, tool_name: str, args: Mapping[str, Any]) -> bool:
        """Drop a cached entry if present.

        Args:
            tool_name: Tool name (non-empty).
            args: Tool arguments mapping.

        Returns:
            True when an entry was removed; False on miss.

        Raises:
            ValueError: When ``tool_name`` is empty.
            TypeError: When ``args`` is not a mapping.
        """

        if not tool_name.strip():
            raise ValueError("tool_name must be non-empty")
        if not isinstance(args, Mapping):
            raise TypeError("args must be a mapping")
        key = self.make_key(tool_name.strip(), dict(args))
        return self._entries.pop(key, None) is not None
