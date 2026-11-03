# AgentTokenBudgetSkewBandAdvisor Guide

![AgentTokenBudgetSkewBandAdvisor](../../assets/demo/agent-token-budget-skew.gif)

Offline helper.
Gap vs LangGraph/CrewAI/AutoGen agent token-budget skew monitors. Distinct from `SessionTokenBudgetLedger` / `CriticTokenBudgetBandGuard`.

Stack: **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

## Usage

```python
from multi_bot_agentic.agent_token_budget_skew_band import AgentTokenBudgetSkewBandAdvisor

status = AgentTokenBudgetSkewBandAdvisor().advise("session-1", skew_ratio=0.3)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Advisory only. No network I/O. Never auto-acts. Humans decide.
