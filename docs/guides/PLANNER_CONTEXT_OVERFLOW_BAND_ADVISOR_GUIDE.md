# PlannerContextOverflowBandAdvisor Guide

![PlannerContextOverflowBandAdvisor](../../assets/demo/planner-context-overflow.gif)

Offline HITL `overflow_ratio` bands.
Gap vs LangGraph/CrewAI/AutoGen planner context-overflow monitors. Distinct from `PlannerStepBudgetBandAdvisor` / `PlannerHorizonBandAdvisor`.

Stack: **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Usage

```python
from multi_bot_agentic.planner_context_overflow_band import PlannerContextOverflowBandAdvisor

status = PlannerContextOverflowBandAdvisor().advise("session-1", overflow_ratio=0.3)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Advisory only. No network I/O. Never auto-acts.
