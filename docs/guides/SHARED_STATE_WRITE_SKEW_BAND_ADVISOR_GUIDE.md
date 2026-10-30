# SharedStateWriteSkewBandAdvisor Guide

![SharedStateWriteSkewBandAdvisor](../../assets/demo/shared-state-write-skew.gif)

HITL band advisor for `write_skew_ratio`.
Gap vs LangGraph/CrewAI/AutoGen shared-state write-skew monitors. Distinct from `SharedMemoryQuotaThrashBandAdvisor` / `SharedLockContentionBandAdvisor`.

Stack: **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

## Usage

```python
from multi_bot_agentic.shared_state_write_skew_band import SharedStateWriteSkewBandAdvisor

status = SharedStateWriteSkewBandAdvisor().advise("session-1", write_skew_ratio=0.3)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Advisory only. No network I/O. Humans decide.
