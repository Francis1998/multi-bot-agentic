"""BlackboardCasWriteSkewGuard band guard.

Flags write_skew_score pressure with HITL bands. Distinct from
`SharedBlackboardWriteLease` / `BlackboardWriteAmplificationGuard`.
Fills a gap vs AutoGen/CrewAI/LangGraph shared-blackboard CAS/write-skew guards.
Works with frontier multi-LLM stacks. Never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BlackboardCasWriteSkewStatus:
    """BlackboardCasWriteSkewGuard status."""

    session_id: str
    write_skew_score: float
    soft_limit: float
    hard_limit: float
    band: str
    requires_human_review: bool


class BlackboardCasWriteSkewGuard:
    """Gate write_skew_score vs soft/hard limits."""

    def __init__(self, *, soft_limit: float = 0.6, hard_limit: float = 0.9) -> None:
        """Initialize limits.

        Args:
            soft_limit: Soft max (> 0).
            hard_limit: Hard max (> soft_limit).
        """

        if soft_limit <= 0:
            raise ValueError("soft_limit must be > 0")
        if hard_limit <= soft_limit:
            raise ValueError("hard_limit must be > soft_limit")
        self._soft = soft_limit
        self._hard = hard_limit

    def advise(self, session_id: str, *, write_skew_score: float) -> BlackboardCasWriteSkewStatus:
        """Return band for observed write_skew_score.

        Args:
            session_id: Non-empty id.
            write_skew_score: Observed value (>= 0).

        Returns:
            BlackboardCasWriteSkewStatus with ``requires_human_review=True``.
        """

        sid = session_id.strip()
        if not sid:
            raise ValueError("session_id must be non-empty")
        if write_skew_score < 0:
            raise ValueError("write_skew_score must be >= 0")

        if write_skew_score <= self._soft:
            band = "ok"
        elif write_skew_score <= self._hard:
            band = "elevated"
        else:
            band = "blocked"

        return BlackboardCasWriteSkewStatus(
            session_id=sid,
            write_skew_score=float(write_skew_score),
            soft_limit=self._soft,
            hard_limit=self._hard,
            band=band,
            requires_human_review=True,
        )
