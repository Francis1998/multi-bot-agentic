# ToolPermissionDriftAdvisor Guide

![ToolPermissionDriftAdvisor](../../assets/demo/tool-permission-drift.gif)

Offline HITL advisor for `drift_ratio` bands.
Gap vs LangGraph/CrewAI/AutoGen tool-permission drift monitors. Distinct from `ToolPermissionEscalationBandAdvisor` / `BotCapabilityDriftAdvisor`.

Optional polish via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Usage

```python
from multi_bot_agentic.tool_permission_drift import ToolPermissionDriftAdvisor

status = ToolPermissionDriftAdvisor().advise("s1", drift_ratio=0.3)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Advisory only. No network I/O. Humans decide.
