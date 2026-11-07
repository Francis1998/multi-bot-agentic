# ToolBudgetExhaustionBandAdvisor Guide

![ToolBudgetExhaustionBandAdvisor](../../assets/demo/tool-budget-exhaustion.gif)

Offline HITL helper for `exhaustion_ratio` bands.
Gap vs LangGraph/CrewAI/AutoGen tool budget-exhaustion monitors. Distinct from `ToolCallQuotaGuard` / `ToolRetryBudgetBandGuard`.

Stack: **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Usage

```python
from multi_bot_agentic.tool_budget_exhaustion_band import ToolBudgetExhaustionBandAdvisor

status = ToolBudgetExhaustionBandAdvisor().advise("s1", exhaustion_ratio=0.4)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Advisory only. No network I/O. Never auto-acts. Humans decide.
