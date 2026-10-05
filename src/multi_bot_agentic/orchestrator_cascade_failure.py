"""OrchestratorCascadeFailure guard/advisor.

Flags cascade_depth pressure with HITL bands. Distinct from
``OrchestratorFairnessAgingAdvisor`` and ``DeadLetterToolQueue``.
Fills a gap vs AutoGen/CrewAI/LangGraph orchestrator cascade-failure advisors.
Works with frontier multi-LLM stacks. Never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OrchestratorCascadeFailureStatus:
    """OrchestratorCascadeFailureAdvisor status."""

    session_id: str
    cascade_depth: float
    soft_limit: float
    hard_limit: float
    band: str
    requires_human_review: bool


class OrchestratorCascadeFailureAdvisor:
    """Gate cascade_depth vs soft/hard limits."""

    def __init__(self, *, soft_limit: float = 2.0, hard_limit: float = 4.0) -> None:
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

    def advise(self, session_id: str, *, cascade_depth: float) -> OrchestratorCascadeFailureStatus:
        """Return band for observed cascade_depth.

        Args:
            session_id: Non-empty id.
            cascade_depth: Observed value (``>= 0``).

        Returns:
            OrchestratorCascadeFailureStatus with ``requires_human_review=True``.
        """

        sid = session_id.strip()
        if not sid:
            raise ValueError("session_id must be non-empty")
        if cascade_depth < 0:
            raise ValueError("cascade_depth must be >= 0")

        if cascade_depth <= self._soft:
            band = "ok"
        elif cascade_depth <= self._hard:
            band = "elevated"
        else:
            band = "blocked"

        return OrchestratorCascadeFailureStatus(
            session_id=sid,
            cascade_depth=float(cascade_depth),
            soft_limit=self._soft,
            hard_limit=self._hard,
            band=band,
            requires_human_review=True,
        )
