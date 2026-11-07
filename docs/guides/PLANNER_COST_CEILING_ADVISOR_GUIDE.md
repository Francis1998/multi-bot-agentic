# PlannerCostCeilingAdvisor Guide

![PlannerCostCeilingAdvisor HITL flow](../../assets/demo/planner-cost-ceiling-advisor.gif)

Offline HITL guard/advisor. Never auto-acts. Closes closed-UI gaps vs AutoGen/CrewAI/LangGraph planner cost ceiling controls.

Optional later polish via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

Distinct from `PlannerReplanBudgetLimiter and BudgetedStepPlanner`.

## Usage

```python
from multi_bot_agentic.planner_cost_ceiling import PlannerCostCeilingAdvisor

status = PlannerCostCeilingAdvisor().advise("session-1", cost_usd=3.0)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Always `requires_human_review=True`. No HTTP. Humans decide. See `docs/SAFETY.md`.
