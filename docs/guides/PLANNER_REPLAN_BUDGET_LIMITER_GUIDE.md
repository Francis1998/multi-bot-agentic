# PlannerReplanBudgetLimiter Guide

![PlannerReplanBudgetLimiter](../../assets/demo/planner-replan-budget-limiter.gif)

Offline HITL limiter. Caps planner replan loops. Closes gaps vs AutoGen /
CrewAI / LangGraph unbounded replanning.

Optional later polish via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

Distinct from `BudgetedStepPlanner` and `CriticPassBudgetLimiter`.

## Usage

```python
from multi_bot_agentic.planner_replan_budget import PlannerReplanBudgetLimiter

status = PlannerReplanBudgetLimiter().check("s1", replan_count=2, max_replans=3)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Always `requires_human_review=True`. No HTTP. Humans decide. See `SAFETY.md`.
