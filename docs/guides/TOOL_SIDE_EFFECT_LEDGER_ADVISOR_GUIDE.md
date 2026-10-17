# ToolSideEffectLedgerAdvisor Guide

![ToolSideEffectLedgerAdvisor](../../assets/demo/tool-side-effect-ledger.gif)

Offline HITL advisor for `side_effect_ratio` bands. Gap vs LangGraph/CrewAI/AutoGen tool side-effect ledger monitors. Distinct from `ToolCallQuotaGuard` / `ToolIdempotencyCache`.

Optional polish via **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

## Usage

```python
from multi_bot_agentic.tool_side_effect_ledger import ToolSideEffectLedgerAdvisor

status = ToolSideEffectLedgerAdvisor().advise("s1", side_effect_ratio=0.3)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Advisory only. No network I/O. Humans decide.
