# ToolTimeoutCascadeBandAdvisor Guide

![ToolTimeoutCascadeBandAdvisor](../../assets/demo/tool-timeout-cascade-band.gif)

Offline HITL `cascade_ratio` bands. Gap vs LangGraph/CrewAI/AutoGen tool-timeout cascade monitors. Distinct from `HandoffTimeoutBandAdvisor` / `CriticTimeoutBandAdvisor`.

Optional polish via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Usage

```python
from multi_bot_agentic.tool_timeout_cascade_band import ToolTimeoutCascadeBandAdvisor

status = ToolTimeoutCascadeBandAdvisor().advise("s1", cascade_ratio=0.3)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Advisory only. No network I/O. Humans decide.
