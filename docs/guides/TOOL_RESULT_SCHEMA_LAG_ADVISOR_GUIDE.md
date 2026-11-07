# ToolResultSchemaLagAdvisor Guide

![ToolResultSchemaLagAdvisor](../../assets/demo/tool-result-schema-lag.gif)

Offline HITL advisor for `lag_ratio` bands. Gap vs LangGraph/CrewAI/AutoGen tool-result schema lag monitors. Distinct from `ToolArgSchemaDriftGuard` / `ToolResultSchemaHashAdvisor`.

Optional polish via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Usage

```python
from multi_bot_agentic.tool_result_schema_lag import ToolResultSchemaLagAdvisor

status = ToolResultSchemaLagAdvisor().advise("s1", lag_ratio=0.3)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Advisory only. No network I/O. Humans decide.
