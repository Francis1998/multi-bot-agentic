# HitlTimeoutCascadeBandAdvisor Guide

![HitlTimeoutCascadeBandAdvisor](../../assets/demo/hitl-timeout-cascade.gif)

Offline helper.
Gap vs LangGraph/CrewAI/AutoGen HITL timeout-cascade monitors. Distinct from `HandoffTimeoutBandAdvisor` / `ToolTimeoutCascadeBandAdvisor`.

Stack: **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Usage

```python
from multi_bot_agentic.hitl_timeout_cascade_band import HitlTimeoutCascadeBandAdvisor

status = HitlTimeoutCascadeBandAdvisor().advise("session-1", cascade_ratio=0.35)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Advisory only. No network I/O. Never auto-acts. Humans decide.
