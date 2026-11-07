# SubgraphRetryAmplificationBandAdvisor Guide

![SubgraphRetryAmplificationBandAdvisor](../../assets/demo/subgraph-retry-amplification.gif)

Offline helper.
Gap vs LangGraph/CrewAI/AutoGen subgraph retry-amplification monitors. Distinct from `ToolRetryBudgetBandGuard` / `ToolTimeoutCascadeBandAdvisor`.

Stack: **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Usage

```python
from multi_bot_agentic.subgraph_retry_amplification_band import SubgraphRetryAmplificationBandAdvisor

status = SubgraphRetryAmplificationBandAdvisor().advise("session-1", amplification_ratio=0.35)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Advisory only. No network I/O. Never auto-acts. Humans decide.
