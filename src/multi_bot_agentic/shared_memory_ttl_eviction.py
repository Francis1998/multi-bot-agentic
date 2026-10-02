"""Shared-memory TTL eviction advisor.

Advises shared-memory TTL eviction pressure with HITL bands. Distinct from
``BlackboardEntryTtlEvictor`` and ``SharedMemoryQuotaGuard``.
Fills a gap vs AutoGen/CrewAI/LangGraph shared-memory TTL eviction advisors.
Works with GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x /
Kimi K2. Never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SharedMemoryTtlEvictionStatus:
    """Shared-memory TTL eviction status."""

    session_id: str
    expired_ratio: float
    soft_limit: float
    hard_limit: float
    band: str
    requires_human_review: bool


class SharedMemoryTtlEvictionAdvisor:
    """Advise shared-memory expired-entry ratio bands."""

    def __init__(self, *, soft_limit: float = 0.2, hard_limit: float = 0.5) -> None:
        """Initialize expired-ratio limits.

        Args:
            soft_limit: Soft max expired ratio (``> 0``).
            hard_limit: Hard max expired ratio (``> soft_limit``).
        """

        if soft_limit <= 0:
            raise ValueError("soft_limit must be > 0")
        if hard_limit <= soft_limit:
            raise ValueError("hard_limit must be > soft_limit")
        self._soft = soft_limit
        self._hard = hard_limit

    def advise(self, session_id: str, *, expired_ratio: float) -> SharedMemoryTtlEvictionStatus:
        """Return TTL eviction band.

        Args:
            session_id: Non-empty session id.
            expired_ratio: Expired entries / total (``0..1``).

        Returns:
            SharedMemoryTtlEvictionStatus with ``requires_human_review=True``.
        """

        sid = session_id.strip()
        if not sid:
            raise ValueError("session_id must be non-empty")
        if expired_ratio < 0.0 or expired_ratio > 1.0:
            raise ValueError("expired_ratio must be in [0, 1]")

        if expired_ratio <= self._soft:
            band = "ok"
        elif expired_ratio <= self._hard:
            band = "elevated"
        else:
            band = "blocked"

        return SharedMemoryTtlEvictionStatus(
            session_id=sid,
            expired_ratio=float(expired_ratio),
            soft_limit=self._soft,
            hard_limit=self._hard,
            band=band,
            requires_human_review=True,
        )
