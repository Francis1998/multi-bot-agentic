# PlannerGoalDriftGuard Guide

![PlannerGoalDriftGuard](../../assets/demo/planner-goal-drift-guard.gif)

Offline HITL guard. Flags planner step goals that drift from the plan goal.
Closes AutoGen / CrewAI / LangGraph planner goal-drift gaps.

Optional polish via **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

Distinct from `PlannerReplanBudgetLimiter` and `PlanStepDependencyResolver`.

## Usage

```python
from multi_bot_agentic.planner_goal_drift import PlannerGoalDriftGuard

status = PlannerGoalDriftGuard().check(
    "s1",
    plan_goal="summarize research papers",
    step_goal="book flight tickets",
)
assert status.requires_human_review is True
print(status.band, status.overlap_ratio)
```

## Safety

Always `requires_human_review=True`. No HTTP. Humans decide.
