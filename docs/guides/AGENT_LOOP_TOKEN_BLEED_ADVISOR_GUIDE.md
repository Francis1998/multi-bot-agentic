# AgentLoopTokenBleedAdvisor Guide

![AgentLoopTokenBleedAdvisor](../../assets/demo/agent-loop-token-bleed.gif)

Offline HITL advisor for `token_bleed_ratio` bands.
Gap vs LangGraph/CrewAI/AutoGen agent-loop token-bleed monitors. Distinct from `PlannerCriticOscillationBandAdvisor` / `MemoryNamespaceLeakAdvisor`.

Optional polish via **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

## Usage

```python
from multi_bot_agentic.agent_loop_token_bleed import AgentLoopTokenBleedAdvisor

status = AgentLoopTokenBleedAdvisor().advise("session-1", token_bleed_ratio=0.4)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Advisory only. No network I/O. Never auto-acts. Humans decide.
