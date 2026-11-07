# ToolResultSizeBombGuard Guide

![ToolResultSizeBombGuard HITL flow](../../assets/demo/tool-result-size-bomb.gif)

Offline HITL guard. Never network I/O. Closes gaps vs AutoGen/CrewAI/LangGraph tool-result size-bomb guards.

Optional polish via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

Distinct from `ToolArgByteBudgetGuard` / `ToolResultPoisoningGuard`.

## Usage

```python
from multi_bot_agentic.tool_result_size_bomb import ToolResultSizeBombGuard

status = ToolResultSizeBombGuard().check("s1", result_bytes=0.1)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Always `requires_human_review=True`. No HTTP. Humans decide.
