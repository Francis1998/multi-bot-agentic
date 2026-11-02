# PlannerGoalChurnBandAdvisor Guide

![PlannerGoalChurnBandAdvisor](../../assets/demo/planner-goal-churn.gif)

Offline HITL band guard for `churn_ratio`.
Gap vs LangGraph/CrewAI/AutoGen planner goal-churn monitors. Distinct from `PlannerContextOverflowBandAdvisor` / `PlanGoalContradictionBandAdvisor`.

Works with **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

## Usage

```python
from multi_bot_agentic.planner_goal_churn_band import PlannerGoalChurnBandAdvisor

status = PlannerGoalChurnBandAdvisor().advise("session-1", churn_ratio=0.3)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Advisory only. No network I/O. Humans decide.
