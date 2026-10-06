# PlannerDepthCapAdvisor Guide

![PlannerDepthCapAdvisor HITL flow](../../assets/demo/planner-depth-cap-advisor.gif)

Offline HITL guard/advisor. Never auto-acts. Closes closed-UI gaps vs AutoGen/CrewAI/LangGraph planner depth caps.

Optional later polish via **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

Distinct from ``PlannerCostCeilingAdvisor`` and ``PlannerBeamWidthLimiter``.

## Usage

```python
from multi_bot_agentic.planner_depth_cap import PlannerDepthCapAdvisor

status = PlannerDepthCapAdvisor().advise("session-1", plan_depth=10.0)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Always `requires_human_review=True`. No HTTP. Humans decide. See `docs/SAFETY.md`.
