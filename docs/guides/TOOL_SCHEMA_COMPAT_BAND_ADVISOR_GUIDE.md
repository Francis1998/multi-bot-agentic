# ToolSchemaCompatBandAdvisor Guide

![ToolSchemaCompatBandAdvisor](../../assets/demo/tool-schema-compat.gif)

Offline helper.
Gap vs LangGraph/CrewAI/AutoGen tool-schema compatibility monitors. Distinct from `ToolResultSchemaDriftBandAdvisor` / `ToolBudgetExhaustionBandAdvisor`.

Stack: **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Usage

```python
from multi_bot_agentic.tool_schema_compat_band import ToolSchemaCompatBandAdvisor

status = ToolSchemaCompatBandAdvisor().advise("session-1", compat_ratio=0.3)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Advisory only. No network I/O. Never auto-acts. Humans decide.
