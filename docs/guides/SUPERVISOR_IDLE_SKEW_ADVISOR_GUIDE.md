# SupervisorIdleSkewAdvisor Guide

![SupervisorIdleSkewAdvisor](../../assets/demo/supervisor-idle-skew.gif)

Offline HITL helper for `idle_skew_ratio` bands.
Gap vs LangGraph/CrewAI/AutoGen supervisor idle-skew monitors. Distinct from `WorkerStarvationBandAdvisor` / `OrchestratorRetryStormBandAdvisor`.

Optional polish via **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

## Usage

```python
from multi_bot_agentic.supervisor_idle_skew import SupervisorIdleSkewAdvisor

status = SupervisorIdleSkewAdvisor().advise("session-1", idle_skew_ratio=0.4)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Advisory only. No network I/O. Never auto-acts. Humans decide.
