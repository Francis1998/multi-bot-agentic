"""Planner replan budget limiter.

Caps how many times a planner may replan within a session and emits HITL
bands. Distinct from ``BudgetedStepPlanner`` (step costing) and
``CriticPassBudgetLimiter`` (critic passes). Fills a gap vs AutoGen /
CrewAI / LangGraph unbounded replanning loops. Works with GPT-5.5 /
Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. Never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlannerReplanBudgetStatus:
    """Planner replan budget status."""

    session_id: str
    replan_count: int
    max_replans: int
    band: str
    requires_human_review: bool


class PlannerReplanBudgetLimiter:
    """Limit planner replan attempts per session."""

    def check(
        self,
        session_id: str,
        *,
        replan_count: int,
        max_replans: int = 3,
    ) -> PlannerReplanBudgetStatus:
        """Return replan budget band for a session.

        Args:
            session_id: Non-empty session id.
            replan_count: Replans already used (``>= 0``).
            max_replans: Maximum allowed replans (``> 0``).

        Returns:
            PlannerReplanBudgetStatus with ``requires_human_review=True``.
        """

        sid = session_id.strip()
        if not sid:
            raise ValueError("session_id must be non-empty")
        if replan_count < 0:
            raise ValueError("replan_count must be >= 0")
        if max_replans <= 0:
            raise ValueError("max_replans must be > 0")

        if replan_count >= max_replans:
            band = "exhausted"
        elif replan_count >= max(1, int(max_replans * 0.66)):
            band = "warning"
        else:
            band = "ok"

        return PlannerReplanBudgetStatus(
            session_id=sid,
            replan_count=int(replan_count),
            max_replans=int(max_replans),
            band=band,
            requires_human_review=True,
        )
