# ToolResultSchemaLagAdvisor Guide

![ToolResultSchemaLagAdvisor](../../assets/demo/tool-result-schema-lag.gif)

Offline HITL advisor for `lag_ratio` bands. Gap vs LangGraph/CrewAI/AutoGen tool-result schema lag monitors. Distinct from `ToolArgSchemaDriftGuard` / `ToolResultSchemaHashAdvisor`.

Optional polish via **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

## Usage

```python
from multi_bot_agentic.tool_result_schema_lag import ToolResultSchemaLagAdvisor

status = ToolResultSchemaLagAdvisor().advise("s1", lag_ratio=0.3)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Advisory only. No network I/O. Humans decide.
