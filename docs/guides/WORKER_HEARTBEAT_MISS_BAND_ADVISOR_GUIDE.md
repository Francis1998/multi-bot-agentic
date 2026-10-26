# WorkerHeartbeatMissBandAdvisor Guide

![WorkerHeartbeatMissBandAdvisor](../../assets/demo/worker-heartbeat-miss.gif)

Offline HITL `miss_ratio` bands.
Gap vs LangGraph/CrewAI/AutoGen worker heartbeat-miss monitors. Distinct from `SupervisorRestartThrashAdvisor` / `SupervisorIdleSkewAdvisor`.

Stack: **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

## Usage

```python
from multi_bot_agentic.worker_heartbeat_miss_band import WorkerHeartbeatMissBandAdvisor

status = WorkerHeartbeatMissBandAdvisor().advise("session-1", miss_ratio=0.4)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Advisory only. No network I/O. Never auto-acts.
