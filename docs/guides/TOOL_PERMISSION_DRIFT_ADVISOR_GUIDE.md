# ToolPermissionDriftAdvisor Guide

![ToolPermissionDriftAdvisor](../../assets/demo/tool-permission-drift.gif)

Offline HITL advisor for `drift_ratio` bands.
Gap vs LangGraph/CrewAI/AutoGen tool-permission drift monitors. Distinct from `ToolPermissionEscalationBandAdvisor` / `BotCapabilityDriftAdvisor`.

Optional polish via **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

## Usage

```python
from multi_bot_agentic.tool_permission_drift import ToolPermissionDriftAdvisor

status = ToolPermissionDriftAdvisor().advise("s1", drift_ratio=0.3)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Advisory only. No network I/O. Humans decide.
