"""TTL eviction helper for SharedBlackboard entries.

Tracks per-key write timestamps and reports expired keys for eviction.
Distinct from ``SessionTtlExpirer`` (session idle TTL) and
``SharedBlackboard`` (typed scratchpad with revision caps). Fills a gap vs
AutoGen / CrewAI / LangGraph shared-memory stores that often lack explicit
per-entry TTL eviction. Works with GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x /
Kimi K2. Never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True)
class BlackboardTtlStatus:
    """TTL status for one blackboard key.

    Attributes:
        key: Blackboard entry key.
        ttl_seconds: Configured TTL.
        age_seconds: Seconds since last touch.
        expired: True when age >= ttl.
        expires_at: Absolute expiry timestamp.
    """

    key: str
    ttl_seconds: float
    age_seconds: float
    expired: bool
    expires_at: datetime


class BlackboardEntryTtlEvictor:
    """Track blackboard key ages and list expired keys for eviction."""

    def __init__(self, *, ttl_seconds: float = 300.0) -> None:
        """Create a TTL evictor.

        Args:
            ttl_seconds: Entry TTL in seconds (must be > 0).

        Raises:
            ValueError: When ttl_seconds <= 0.
        """

        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be > 0")
        self._ttl = float(ttl_seconds)
        self._touched: dict[str, datetime] = {}

    @property
    def ttl_seconds(self) -> float:
        """Return configured TTL seconds."""

        return self._ttl

    def touch(self, key: str, *, now: datetime | None = None) -> BlackboardTtlStatus:
        """Record a write/read touch for ``key`` and return status.

        Args:
            key: Non-empty blackboard key.
            now: Optional clock override (UTC-aware preferred).

        Returns:
            BlackboardTtlStatus after the touch (age ~0).
        """

        k = key.strip()
        if not k:
            raise ValueError("key must be non-empty")
        stamp = now or datetime.now(timezone.utc)
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        self._touched[k] = stamp
        return self.status(k, now=stamp)

    def status(self, key: str, *, now: datetime | None = None) -> BlackboardTtlStatus:
        """Return TTL status for ``key``.

        Raises:
            ValueError: When key empty or unknown.
        """

        k = key.strip()
        if not k:
            raise ValueError("key must be non-empty")
        if k not in self._touched:
            raise ValueError(f"unknown key: {k}")
        stamp = self._touched[k]
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        age = (current - stamp).total_seconds()
        expired = age >= self._ttl
        return BlackboardTtlStatus(
            key=k,
            ttl_seconds=self._ttl,
            age_seconds=age,
            expired=expired,
            expires_at=stamp + timedelta(seconds=self._ttl),
        )

    def expired_keys(self, *, now: datetime | None = None) -> tuple[str, ...]:
        """Return expired keys in insertion order."""

        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        out: list[str] = []
        for key, stamp in self._touched.items():
            if (current - stamp).total_seconds() >= self._ttl:
                out.append(key)
        return tuple(out)

    def evict_expired(self, *, now: datetime | None = None) -> tuple[str, ...]:
        """Remove and return expired keys."""

        doomed = self.expired_keys(now=now)
        for key in doomed:
            self._touched.pop(key, None)
        return doomed
