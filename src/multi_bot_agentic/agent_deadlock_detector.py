"""AgentDeadlockDetectorGuard band guard.

Flags deadlock_score pressure with HITL bands. Distinct from
`PlanStepCycleDetectorGuard` / `OrchestratorCascadeFailureAdvisor`.
Fills a gap vs AutoGen/CrewAI/LangGraph agent-deadlock detectors.
Works with frontier multi-LLM stacks. Never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentDeadlockDetectorStatus:
    """AgentDeadlockDetectorGuard status."""

    session_id: str
    deadlock_score: float
    soft_limit: float
    hard_limit: float
    band: str
    requires_human_review: bool


class AgentDeadlockDetectorGuard:
    """Gate deadlock_score vs soft/hard limits."""

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

    def check(self, session_id: str, *, deadlock_score: float) -> AgentDeadlockDetectorStatus:
        """Return band for observed deadlock_score.

        Args:
            session_id: Non-empty id.
            deadlock_score: Observed value (``>= 0``).

        Returns:
            AgentDeadlockDetectorStatus with ``requires_human_review=True``.
        """

        sid = session_id.strip()
        if not sid:
            raise ValueError("session_id must be non-empty")
        if deadlock_score < 0:
            raise ValueError("deadlock_score must be >= 0")

        if deadlock_score <= self._soft:
            band = "ok"
        elif deadlock_score <= self._hard:
            band = "elevated"
        else:
            band = "blocked"

        return AgentDeadlockDetectorStatus(
            session_id=sid,
            deadlock_score=float(deadlock_score),
            soft_limit=self._soft,
            hard_limit=self._hard,
            band=band,
            requires_human_review=True,
        )
