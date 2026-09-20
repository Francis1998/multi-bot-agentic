"""Exclusive write-lease helper for SharedBlackboard keys.

Grants time-bounded exclusive write leases per key so concurrent bots do not
silently overwrite each other. Distinct from ``BlackboardEntryTtlEvictor``
(read/write TTL eviction) and ``SharedBlackboard`` (typed scratchpad). Fills a
gap vs AutoGen / CrewAI / LangGraph shared-memory stores that often lack
explicit write leases. Works with GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x /
Kimi K2. Never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True)
class BlackboardLeaseStatus:
    """Write-lease status for one blackboard key.

    Attributes:
        key: Blackboard entry key.
        holder: Bot id holding the lease, if any.
        acquired: True when this call acquired/refreshed the lease.
        expired: True when a prior lease is past TTL.
        allowed: True when the caller may write under mode.
        mode: ``advisory`` or ``hard``.
    """

    key: str
    holder: str | None
    acquired: bool
    expired: bool
    allowed: bool
    mode: str


class SharedBlackboardWriteLease:
    """Grant exclusive time-bounded write leases on blackboard keys."""

    def __init__(self, *, lease_seconds: float = 30.0, mode: str = "advisory") -> None:
        """Create a write-lease manager.

        Args:
            lease_seconds: Lease TTL in seconds (must be > 0).
            mode: ``advisory`` keeps ``allowed=True`` on conflict;
                ``hard`` sets ``allowed=False``.

        Raises:
            ValueError: On invalid lease_seconds or mode.
        """

        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be > 0")
        if mode not in {"advisory", "hard"}:
            raise ValueError("mode must be 'advisory' or 'hard'")
        self._lease_seconds = float(lease_seconds)
        self._mode = mode
        self._leases: dict[str, tuple[str, datetime]] = {}

    @property
    def mode(self) -> str:
        """Return configured enforcement mode."""

        return self._mode

    def acquire(
        self,
        key: str,
        bot_id: str,
        *,
        now: datetime | None = None,
    ) -> BlackboardLeaseStatus:
        """Try to acquire or refresh a write lease for ``key``.

        Args:
            key: Non-empty blackboard key.
            bot_id: Non-empty bot id requesting the lease.
            now: Optional clock override.

        Returns:
            BlackboardLeaseStatus for this attempt.
        """

        k = key.strip()
        bid = bot_id.strip()
        if not k:
            raise ValueError("key must be non-empty")
        if not bid:
            raise ValueError("bot_id must be non-empty")
        stamp = now or datetime.now(timezone.utc)
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)

        current = self._leases.get(k)
        expired = False
        if current is not None:
            holder, expires_at = current
            if stamp >= expires_at:
                expired = True
                current = None
                del self._leases[k]
            elif holder == bid:
                self._leases[k] = (bid, stamp + timedelta(seconds=self._lease_seconds))
                return BlackboardLeaseStatus(
                    key=k,
                    holder=bid,
                    acquired=True,
                    expired=False,
                    allowed=True,
                    mode=self._mode,
                )
            else:
                allowed = self._mode == "advisory"
                return BlackboardLeaseStatus(
                    key=k,
                    holder=holder,
                    acquired=False,
                    expired=False,
                    allowed=allowed,
                    mode=self._mode,
                )

        self._leases[k] = (bid, stamp + timedelta(seconds=self._lease_seconds))
        return BlackboardLeaseStatus(
            key=k,
            holder=bid,
            acquired=True,
            expired=expired,
            allowed=True,
            mode=self._mode,
        )

    def release(self, key: str, bot_id: str) -> bool:
        """Release a lease if ``bot_id`` is the current holder."""

        k = key.strip()
        bid = bot_id.strip()
        if not k or not bid:
            raise ValueError("key and bot_id must be non-empty")
        current = self._leases.get(k)
        if current is None or current[0] != bid:
            return False
        del self._leases[k]
        return True
