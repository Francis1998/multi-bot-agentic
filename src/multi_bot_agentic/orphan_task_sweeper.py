"""OrphanTaskSweeperGuard band guard.

Flags orphan_count pressure with HITL bands. Distinct from
`DeadLetterToolQueue` / `RunDeadlineWatchdog`.
Fills a gap vs AutoGen/CrewAI/LangGraph orphan-task sweepers.
Works with frontier multi-LLM stacks. Never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OrphanTaskSweeperStatus:
    """OrphanTaskSweeperGuard status."""

    session_id: str
    orphan_count: float
    soft_limit: float
    hard_limit: float
    band: str
    requires_human_review: bool


class OrphanTaskSweeperGuard:
    """Gate orphan_count vs soft/hard limits."""

    def __init__(self, *, soft_limit: float = 0.2, hard_limit: float = 0.6) -> None:
        """Initialize limits.

        Args:
            soft_limit: Soft max (``> 0``).
            hard_limit: Hard max (``> soft_limit``).
        """

        if soft_limit <= 0:
            raise ValueError("soft_limit must be > 0")
        if hard_limit <= soft_limit:
            raise ValueError("hard_limit must be > soft_limit")
        self._soft = soft_limit
        self._hard = hard_limit

    def check(self, session_id: str, *, orphan_count: float) -> OrphanTaskSweeperStatus:
        """Return band for observed orphan_count.

        Args:
            session_id: Non-empty id.
            orphan_count: Observed value (``>= 0``).

        Returns:
            OrphanTaskSweeperStatus with ``requires_human_review=True``.
        """

        sid = session_id.strip()
        if not sid:
            raise ValueError("session_id must be non-empty")
        if orphan_count < 0:
            raise ValueError("orphan_count must be >= 0")

        if orphan_count <= self._soft:
            band = "ok"
        elif orphan_count <= self._hard:
            band = "elevated"
        else:
            band = "blocked"

        return OrphanTaskSweeperStatus(
            session_id=sid,
            orphan_count=float(orphan_count),
            soft_limit=self._soft,
            hard_limit=self._hard,
            band=band,
            requires_human_review=True,
        )
