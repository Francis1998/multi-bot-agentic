# WorkerQueueDepthBandAdvisor Guide

![WorkerQueueDepthBandAdvisor](../../assets/demo/worker-queue-depth.gif)

Offline HITL band guard for `queue_depth_ratio`.
Gap vs LangGraph/CrewAI/AutoGen worker-queue depth monitors. Distinct from `WorkerStarvationBandAdvisor` / `WorkerHeartbeatMissBandAdvisor`.

Works with **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Usage

```python
from multi_bot_agentic.worker_queue_depth_band import WorkerQueueDepthBandAdvisor

status = WorkerQueueDepthBandAdvisor().advise("session-1", queue_depth_ratio=0.3)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Advisory only. No network I/O. Humans decide.
