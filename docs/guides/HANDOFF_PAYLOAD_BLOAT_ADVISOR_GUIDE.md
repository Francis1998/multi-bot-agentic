# HandoffPayloadBloatAdvisor Guide

![HandoffPayloadBloatAdvisor](../../assets/demo/handoff-payload-bloat.gif)

Offline HITL advisor for `payload_bloat_ratio` bands.
Gap vs LangGraph/CrewAI/AutoGen handoff payload-bloat monitors. Distinct from `HandoffTimeoutBandAdvisor` / `ToolTimeoutCascadeBandAdvisor`.

Optional polish via **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

## Usage

```python
from multi_bot_agentic.handoff_payload_bloat import HandoffPayloadBloatAdvisor

status = HandoffPayloadBloatAdvisor().advise("session-1", payload_bloat_ratio=0.4)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Advisory only. No network I/O. Never auto-acts. Humans decide.
