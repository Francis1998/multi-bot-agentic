"""PlannerDepthCap advisor.

Flags plan_depth pressure with HITL bands. Distinct from
``PlannerCostCeilingAdvisor`` and ``PlannerBeamWidthLimiter``.
Fills a gap vs AutoGen/CrewAI/LangGraph planner depth caps.
Works with frontier multi-LLM stacks. Never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlannerDepthCapStatus:
    """PlannerDepthCapAdvisor status."""

    session_id: str
    plan_depth: float
    soft_limit: float
    hard_limit: float
    band: str
    requires_human_review: bool


class PlannerDepthCapAdvisor:
    """Gate plan_depth vs soft/hard limits."""

    def __init__(self, *, soft_limit: float = 5.0, hard_limit: float = 15.0) -> None:
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

    def advise(self, session_id: str, *, plan_depth: float) -> PlannerDepthCapStatus:
        """Return band for observed plan_depth.

        Args:
            session_id: Non-empty id.
            plan_depth: Observed value (``>= 0``).

        Returns:
            PlannerDepthCapStatus with ``requires_human_review=True``.
        """

        sid = session_id.strip()
        if not sid:
            raise ValueError("session_id must be non-empty")
        if plan_depth < 0:
            raise ValueError("plan_depth must be >= 0")

        if plan_depth <= self._soft:
            band = "ok"
        elif plan_depth <= self._hard:
            band = "elevated"
        else:
            band = "blocked"

        return PlannerDepthCapStatus(
            session_id=sid,
            plan_depth=float(plan_depth),
            soft_limit=self._soft,
            hard_limit=self._hard,
            band=band,
            requires_human_review=True,
        )
