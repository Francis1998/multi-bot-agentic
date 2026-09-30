"""Blackboard write-amplification band guard.

Flags write/read amplification on a shared blackboard with HITL bands.
Distinct from ``SharedBlackboardWriteLease`` (lease locking) and
``SharedMemoryConflictBandGuard`` (version skew). Fills a gap vs AutoGen /
CrewAI / LangGraph blackboard write-amplification bands.
Works with GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2.
Never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BlackboardWriteAmplificationStatus:
    """Blackboard write-amplification status."""

    session_id: str
    write_count: int
    read_count: int
    amplification: float
    soft_limit: float
    hard_limit: float
    band: str
    requires_human_review: bool


class BlackboardWriteAmplificationBandGuard:
    """Gate blackboard write amplification vs soft/hard limits."""

    def __init__(self, *, soft_limit: float = 2.0, hard_limit: float = 5.0) -> None:
        """Initialize limits.

        Args:
            soft_limit: Soft amplification ratio (``> 0``).
            hard_limit: Hard amplification ratio (``> soft_limit``).
        """

        if soft_limit <= 0:
            raise ValueError("soft_limit must be > 0")
        if hard_limit <= soft_limit:
            raise ValueError("hard_limit must be > soft_limit")
        self._soft = float(soft_limit)
        self._hard = float(hard_limit)

    def check(
        self,
        session_id: str,
        *,
        write_count: int,
        read_count: int,
    ) -> BlackboardWriteAmplificationStatus:
        """Return amplification band.

        Args:
            session_id: Non-empty session id.
            write_count: Writes observed (``>= 0``).
            read_count: Reads observed (``>= 0``).

        Returns:
            BlackboardWriteAmplificationStatus with ``requires_human_review=True``.
        """

        sid = session_id.strip()
        if not sid:
            raise ValueError("session_id must be non-empty")
        if write_count < 0:
            raise ValueError("write_count must be >= 0")
        if read_count < 0:
            raise ValueError("read_count must be >= 0")

        denom = max(read_count, 1)
        amplification = round(write_count / denom, 4)
        if amplification >= self._hard:
            band = "hard"
        elif amplification >= self._soft:
            band = "soft"
        else:
            band = "ok"

        return BlackboardWriteAmplificationStatus(
            session_id=sid,
            write_count=int(write_count),
            read_count=int(read_count),
            amplification=float(amplification),
            soft_limit=self._soft,
            hard_limit=self._hard,
            band=band,
            requires_human_review=True,
        )
