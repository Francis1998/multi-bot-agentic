# PlannerToolMismatchBandAdvisor Guide

![PlannerToolMismatchBandAdvisor](../assets/demo/planner-tool-mismatch-band.gif)

Offline HITL `mismatch_ratio` bands.
Gap vs LangGraph/CrewAI/AutoGen planner-tool mismatch monitors. Distinct from `PlanGoalContradictionBandAdvisor` / `ToolPermissionDriftAdvisor`.

Stack: **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

## Usage

```python
from multi_bot_agentic.planner_tool_mismatch_band import PlannerToolMismatchBandAdvisor

status = PlannerToolMismatchBandAdvisor().advise("s1", mismatch_ratio=0.4)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Advisory only. No network I/O. Never auto-acts.
