# PlannerDepthCapAdvisor Guide

![PlannerDepthCapAdvisor HITL flow](../../assets/demo/planner-depth-cap-advisor.gif)

Offline HITL guard/advisor. Never auto-acts. Closes closed-UI gaps vs AutoGen/CrewAI/LangGraph planner depth caps.

Optional later polish via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

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
