# PlannerStepBudgetBandAdvisor Guide

![PlannerStepBudgetBandAdvisor HITL flow](../../assets/demo/planner-step-budget-band.gif)

Offline HITL guard. Never network I/O. Closes gaps vs LangGraph/CrewAI/AutoGen planner step-budget monitors.

Optional polish via **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

Distinct from `PlannerDepthCapAdvisor` / `PlannerReplanBudgetAdvisor`.

## Usage

```python
from multi_bot_agentic.planner_step_budget_band import PlannerStepBudgetBandAdvisor

status = PlannerStepBudgetBandAdvisor().advise("s1", steps_used_ratio=0.3000)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Always `requires_human_review=True`. No HTTP. Humans decide.
