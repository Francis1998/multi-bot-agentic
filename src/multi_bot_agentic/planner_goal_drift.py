"""Planner goal drift guard.

Measures token-overlap drift between the original plan goal and the
current step goal, emitting HITL bands. Distinct from
``PlannerReplanBudgetLimiter`` (replan caps) and
``PlanStepDependencyResolver`` (DAG order). Fills a gap vs AutoGen /
CrewAI / LangGraph planner goal-drift checks. Works with GPT-5.5 /
Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. Never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


def _tokens(text: str) -> set[str]:
    return {t for t in text.lower().split() if t}


@dataclass(frozen=True)
class PlannerGoalDriftStatus:
    """Planner goal drift status."""

    session_id: str
    overlap_ratio: float
    band: str
    requires_human_review: bool


class PlannerGoalDriftGuard:
    """Flag planner step goals that drift from the original plan goal."""

    def check(
        self,
        session_id: str,
        *,
        plan_goal: str,
        step_goal: str,
    ) -> PlannerGoalDriftStatus:
        """Return goal-drift band from token overlap.

        Args:
            session_id: Non-empty session id.
            plan_goal: Non-empty original plan goal text.
            step_goal: Non-empty current step goal text.

        Returns:
            PlannerGoalDriftStatus with ``requires_human_review=True``.
        """

        sid = session_id.strip()
        plan = plan_goal.strip()
        step = step_goal.strip()
        if not sid:
            raise ValueError("session_id must be non-empty")
        if not plan:
            raise ValueError("plan_goal must be non-empty")
        if not step:
            raise ValueError("step_goal must be non-empty")

        plan_toks = _tokens(plan)
        step_toks = _tokens(step)
        if not plan_toks or not step_toks:
            raise ValueError("goals must contain tokens")

        overlap = len(plan_toks & step_toks) / len(plan_toks | step_toks)
        ratio = round(overlap, 4)
        if ratio >= 0.5:
            band = "aligned"
        elif ratio >= 0.2:
            band = "drifting"
        else:
            band = "diverged"

        return PlannerGoalDriftStatus(
            session_id=sid,
            overlap_ratio=float(ratio),
            band=band,
            requires_human_review=True,
        )
