"""PlannerCostCeiling advisor.

Flags cost usd pressure with HITL bands. Distinct from
``PlannerReplanBudgetLimiter and BudgetedStepPlanner``.
Fills a gap vs AutoGen/CrewAI/LangGraph planner cost ceiling controls.
Works with GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x /
Kimi K2. Never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlannerCostCeilingStatus:
    """PlannerCostCeilingAdvisor status."""

    plan_id: str
    cost_usd: float
    soft_limit: float
    hard_limit: float
    band: str
    requires_human_review: bool


class PlannerCostCeilingAdvisor:
    """Gate cost usd vs soft/hard limits."""

    def __init__(self, *, soft_limit: float = 1.0, hard_limit: float = 5.0) -> None:
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

    def advise(self, plan_id: str, *, cost_usd: float) -> PlannerCostCeilingStatus:
        """Return band for observed cost_usd.

        Args:
            plan_id: Non-empty id.
            cost_usd: Observed value (``>= 0``).

        Returns:
            PlannerCostCeilingStatus with ``requires_human_review=True``.
        """

        sid = plan_id.strip()
        if not sid:
            raise ValueError("plan_id must be non-empty")
        if cost_usd < 0:
            raise ValueError("cost_usd must be >= 0")

        if cost_usd <= self._soft:
            band = "ok"
        elif cost_usd <= self._hard:
            band = "elevated"
        else:
            band = "blocked"

        return PlannerCostCeilingStatus(
            plan_id=sid,
            cost_usd=float(cost_usd),
            soft_limit=self._soft,
            hard_limit=self._hard,
            band=band,
            requires_human_review=True,
        )
