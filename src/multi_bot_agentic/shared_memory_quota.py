"""Shared-memory (blackboard) write quota guard.

Caps per-bot writes to shared blackboard memory and emits HITL bands.
Distinct from ``SharedBlackboardWriteLease`` (exclusive lease) and
``BlackboardEntryTtlEvictor`` (TTL eviction). Fills a gap vs AutoGen /
CrewAI / LangGraph unbounded shared-state growth. Works with GPT-5.5 /
Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. Never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SharedMemoryQuotaStatus:
    """Per-bot shared-memory write quota status."""

    session_id: str
    bot_id: str
    writes_used: int
    max_writes: int
    remaining: int
    band: str
    requires_human_review: bool


class SharedMemoryQuotaGuard:
    """Guard per-bot shared blackboard write quotas."""

    def check(
        self,
        session_id: str,
        bot_id: str,
        *,
        writes_used: int,
        max_writes: int = 20,
    ) -> SharedMemoryQuotaStatus:
        """Return quota status for one bot in a session.

        Args:
            session_id: Non-empty session id.
            bot_id: Non-empty bot id.
            writes_used: Writes already performed (``>= 0``).
            max_writes: Hard cap (``>= 1``).

        Returns:
            SharedMemoryQuotaStatus with ``requires_human_review=True``.
        """

        sid = session_id.strip()
        bid = bot_id.strip()
        if not sid:
            raise ValueError("session_id must be non-empty")
        if not bid:
            raise ValueError("bot_id must be non-empty")
        if writes_used < 0:
            raise ValueError("writes_used must be >= 0")
        if max_writes < 1:
            raise ValueError("max_writes must be >= 1")

        remaining = max(0, max_writes - writes_used)
        if remaining == 0:
            band = "exhausted"
        elif remaining <= max(1, max_writes // 5):
            band = "near_limit"
        else:
            band = "ok"

        return SharedMemoryQuotaStatus(
            session_id=sid,
            bot_id=bid,
            writes_used=int(writes_used),
            max_writes=int(max_writes),
            remaining=int(remaining),
            band=band,
            requires_human_review=True,
        )
