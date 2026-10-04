# CriticTokenBudgetBandGuard Guide

![CriticTokenBudgetBandGuard HITL flow](../../assets/demo/critic-token-budget-band-guard.gif)

Offline HITL guard/advisor. Never auto-acts. Closes closed-UI gaps vs AutoGen/CrewAI/LangGraph critic token-budget bands.

Optional later polish via **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

Distinct from ``SessionTokenBudgetLedger`` and ``CriticLatencySloBandGuard``.

## Usage

```python
from multi_bot_agentic.critic_token_budget import CriticTokenBudgetBandGuard

status = CriticTokenBudgetBandGuard().check("session-1", tokens_used=5000.0)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Always `requires_human_review=True`. No HTTP. Humans decide. See `docs/SAFETY.md`.
