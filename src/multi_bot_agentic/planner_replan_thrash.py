"""PlannerReplanThrashAdvisor band guard.

Flags replan_thrash_ratio pressure with HITL bands. Distinct from
`PlannerHorizonBandAdvisor` / `PlannerStepBudgetBandAdvisor`.
Fills a gap vs LangGraph/CrewAI/AutoGen planner replan-thrash monitors.
Works with frontier multi-LLM stacks. Never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlannerReplanThrashStatus:
    """PlannerReplanThrashAdvisor status."""

    session_id: str
    replan_thrash_ratio: float
    soft_limit: float
    hard_limit: float
    band: str
    requires_human_review: bool


class PlannerReplanThrashAdvisor:
    """Gate replan_thrash_ratio vs soft/hard limits."""

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

    def advise(self, session_id: str, *, replan_thrash_ratio: float) -> PlannerReplanThrashStatus:
        """Return band for observed replan_thrash_ratio.

        Args:
            session_id: Non-empty id.
            replan_thrash_ratio: Observed value (>= 0).

        Returns:
            PlannerReplanThrashStatus with ``requires_human_review=True``.
        """

        sid = session_id.strip()
        if not sid:
            raise ValueError("session_id must be non-empty")
        if replan_thrash_ratio < 0:
            raise ValueError("replan_thrash_ratio must be >= 0")

        if replan_thrash_ratio <= self._soft:
            band = "ok"
        elif replan_thrash_ratio <= self._hard:
            band = "elevated"
        else:
            band = "blocked"

        return PlannerReplanThrashStatus(
            session_id=sid,
            replan_thrash_ratio=float(replan_thrash_ratio),
            soft_limit=self._soft,
            hard_limit=self._hard,
            band=band,
            requires_human_review=True,
        )
