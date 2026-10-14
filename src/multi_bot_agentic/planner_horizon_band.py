"""PlannerHorizonBandAdvisor band guard.

Flags horizon_steps_ratio pressure with HITL bands. Distinct from
`PlannerStepBudgetBandAdvisor` / `PlannerDepthCapAdvisor`.
Fills a gap vs LangGraph/CrewAI/AutoGen planner-horizon monitors.
Works with frontier multi-LLM stacks. Never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlannerHorizonBandStatus:
    """PlannerHorizonBandAdvisor status."""

    session_id: str
    horizon_steps_ratio: float
    soft_limit: float
    hard_limit: float
    band: str
    requires_human_review: bool


class PlannerHorizonBandAdvisor:
    """Gate horizon_steps_ratio vs soft/hard limits."""

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

    def advise(self, session_id: str, *, horizon_steps_ratio: float) -> PlannerHorizonBandStatus:
        """Return band for observed horizon_steps_ratio.

        Args:
            session_id: Non-empty id.
            horizon_steps_ratio: Observed value (>= 0).

        Returns:
            PlannerHorizonBandStatus with ``requires_human_review=True``.
        """

        sid = session_id.strip()
        if not sid:
            raise ValueError("session_id must be non-empty")
        if horizon_steps_ratio < 0:
            raise ValueError("horizon_steps_ratio must be >= 0")

        if horizon_steps_ratio <= self._soft:
            band = "ok"
        elif horizon_steps_ratio <= self._hard:
            band = "elevated"
        else:
            band = "blocked"

        return PlannerHorizonBandStatus(
            session_id=sid,
            horizon_steps_ratio=float(horizon_steps_ratio),
            soft_limit=self._soft,
            hard_limit=self._hard,
            band=band,
            requires_human_review=True,
        )
