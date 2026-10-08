# AgentHandoffLatencyAdvisor Guide

![AgentHandoffLatencyAdvisor HITL flow](../../assets/demo/agent-handoff-latency.gif)

Offline HITL guard/advisor. Never network I/O. Gap vs AutoGen/CrewAI/LangGraph agent-handoff latency advisors.

Distinct from `AgentHandoffDepthLimiter` / `MultiBotLatencyBudgetAdvisor`.

Optional polish via **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

## Usage

```python
from multi_bot_agentic.agent_handoff_latency import AgentHandoffLatencyAdvisor

status = AgentHandoffLatencyAdvisor().advise("s1", latency_ms=0.1)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Always `requires_human_review=True`. Humans decide.
