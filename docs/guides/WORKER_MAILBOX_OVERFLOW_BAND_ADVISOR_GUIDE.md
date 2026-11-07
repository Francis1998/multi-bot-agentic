# WorkerMailboxOverflowBandAdvisor Guide

![WorkerMailboxOverflowBandAdvisor](../../assets/demo/worker-mailbox-overflow.gif)

Offline helper.
Gap vs LangGraph/CrewAI/AutoGen worker mailbox overflow monitors. Distinct from `WorkerQueueDepthBandAdvisor` / `WorkerStarvationBandAdvisor`.

Stack: **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Usage

```python
from multi_bot_agentic.worker_mailbox_overflow_band import WorkerMailboxOverflowBandAdvisor

status = WorkerMailboxOverflowBandAdvisor().advise("session-1", overflow_ratio=0.35)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Advisory only. No network I/O. Never auto-acts. Humans decide.
