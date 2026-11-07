# HandoffSchemaDriftBandAdvisor Guide

![HandoffSchemaDriftBandAdvisor](../../assets/demo/handoff-schema-drift.gif)

Offline HITL band guard for `drift_ratio`.
Gap vs LangGraph/CrewAI/AutoGen handoff-schema drift monitors. Distinct from `ToolResultSchemaDriftBandAdvisor` / `AgentHandoffLoopBandAdvisor`.

Works with **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Usage

```python
from multi_bot_agentic.handoff_schema_drift_band import HandoffSchemaDriftBandAdvisor

status = HandoffSchemaDriftBandAdvisor().advise("session-1", drift_ratio=0.3)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Advisory only. No network I/O. Humans decide.
