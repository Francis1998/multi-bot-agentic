# AgentAffinitySkewBandAdvisor Guide

![AgentAffinitySkewBandAdvisor](../../assets/demo/agent-affinity-skew.gif)

Offline HITL band guard for `skew_ratio`.
Gap vs LangGraph/CrewAI/AutoGen agent-affinity skew monitors. Distinct from `FanInSkewBandAdvisor` / `SharedStateWriteSkewBandAdvisor`.

Works with **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

## Usage

```python
from multi_bot_agentic.agent_affinity_skew_band import AgentAffinitySkewBandAdvisor

status = AgentAffinitySkewBandAdvisor().advise("session-1", skew_ratio=0.3)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Advisory only. No network I/O. Humans decide.
