# MemoryCompactionLagBandAdvisor Guide

![MemoryCompactionLagBandAdvisor](../../assets/demo/memory-compaction-lag.gif)

Offline helper.
Gap vs LangGraph/CrewAI/AutoGen memory-compaction lag monitors. Distinct from `SharedMemoryQuotaThrashBandAdvisor` / `SharedKvLeaseExpiryBandAdvisor`.

Stack: **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Usage

```python
from multi_bot_agentic.memory_compaction_lag_band import MemoryCompactionLagBandAdvisor

status = MemoryCompactionLagBandAdvisor().advise("session-1", lag_ratio=0.35)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Advisory only. No network I/O. Never auto-acts. Humans decide.
