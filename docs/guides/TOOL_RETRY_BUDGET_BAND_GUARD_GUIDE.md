# ToolRetryBudgetBandGuard Guide

![ToolRetryBudgetBandGuard HITL flow](../../assets/demo/tool-retry-budget-band-guard.gif)

Offline HITL guard/advisor. Never auto-acts. Closes closed-UI gaps vs AutoGen/CrewAI/LangGraph tool-retry budget guards.

Optional later polish via **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

Distinct from ``retry_backoff`` / ``TurnBudgetLimiter``.

## Usage

```python
from multi_bot_agentic.tool_retry_budget import ToolRetryBudgetBandGuard

status = ToolRetryBudgetBandGuard().check("session-1", retry_count=5.0)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Always `requires_human_review=True`. No HTTP. Humans decide. See `docs/SAFETY.md`.
