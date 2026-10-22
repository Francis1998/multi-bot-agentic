# BlackboardReadStalenessAdvisor Guide

![BlackboardReadStalenessAdvisor](../../assets/demo/blackboard-read-staleness.gif)

Offline HITL helper for `staleness_ratio` bands.
Gap vs LangGraph/CrewAI/AutoGen blackboard read-staleness monitors. Distinct from `BlackboardStaleEntryAdvisor` / `BlackboardLeaseThrashAdvisor`.

Optional polish via **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

## Usage

```python
from multi_bot_agentic.blackboard_read_staleness import BlackboardReadStalenessAdvisor

status = BlackboardReadStalenessAdvisor().advise("session-1", staleness_ratio=0.4)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Advisory only. No network I/O. Never auto-acts. Humans decide.
