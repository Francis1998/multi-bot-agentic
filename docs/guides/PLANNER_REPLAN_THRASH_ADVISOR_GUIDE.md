# PlannerReplanThrashAdvisor Guide

![PlannerReplanThrashAdvisor HITL flow](../../assets/demo/planner-replan-thrash.gif)

Offline HITL guard. Never network I/O. Closes gaps vs LangGraph/CrewAI/AutoGen planner replan-thrash monitors.

Optional polish via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

Distinct from `PlannerHorizonBandAdvisor` / `PlannerStepBudgetBandAdvisor`.

## Usage

```python
from multi_bot_agentic.planner_replan_thrash import PlannerReplanThrashAdvisor

status = PlannerReplanThrashAdvisor().advise("s1", replan_thrash_ratio=0.3000)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Always `requires_human_review=True`. No HTTP. Humans decide.
