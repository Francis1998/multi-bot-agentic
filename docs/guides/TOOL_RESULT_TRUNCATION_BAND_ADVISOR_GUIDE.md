# ToolResultTruncationBandAdvisor Guide

![ToolResultTruncationBandAdvisor](../../assets/demo/tool-result-truncation.gif)

HITL band advisor for `truncation_ratio`.
Gap vs LangGraph/CrewAI/AutoGen tool-result truncation monitors. Distinct from `ToolResultSchemaDriftBandAdvisor` / `ToolBudgetExhaustionBandAdvisor`.

Stack: **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Usage

```python
from multi_bot_agentic.tool_result_truncation_band import ToolResultTruncationBandAdvisor

status = ToolResultTruncationBandAdvisor().advise("session-1", truncation_ratio=0.3)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Advisory only. No network I/O. Humans decide.
