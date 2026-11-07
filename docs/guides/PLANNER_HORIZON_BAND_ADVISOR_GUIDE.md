# PlannerHorizonBandAdvisor Guide

![PlannerHorizonBandAdvisor HITL flow](../../assets/demo/planner-horizon-band.gif)

Offline HITL guard. Never network I/O. Closes gaps vs LangGraph/CrewAI/AutoGen planner-horizon monitors.

Optional polish via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

Distinct from `PlannerStepBudgetBandAdvisor` / `PlannerDepthCapAdvisor`.

## Usage

```python
from multi_bot_agentic.planner_horizon_band import PlannerHorizonBandAdvisor

status = PlannerHorizonBandAdvisor().advise("s1", horizon_steps_ratio=0.3000)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Always `requires_human_review=True`. No HTTP. Humans decide.
