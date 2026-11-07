# AgentHandoffLoopBandAdvisor Guide

![AgentHandoffLoopBandAdvisor](../../assets/demo/agent-handoff-loop.gif)

Offline HITL `loop_ratio` bands.
Gap vs LangGraph/CrewAI/AutoGen agent handoff-loop monitors. Distinct from `SubgraphCancelLeakAdvisor` / `PlannerGoalDriftGuard`.

Stack: **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Usage

```python
from multi_bot_agentic.agent_handoff_loop_band import AgentHandoffLoopBandAdvisor

status = AgentHandoffLoopBandAdvisor().advise("session-1", loop_ratio=0.4)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Advisory only. No network I/O. Never auto-acts.
