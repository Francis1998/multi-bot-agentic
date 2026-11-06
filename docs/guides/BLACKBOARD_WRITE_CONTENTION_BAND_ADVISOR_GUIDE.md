# BlackboardWriteContentionBandAdvisor Guide

![BlackboardWriteContentionBandAdvisor](../../assets/demo/blackboard-write-contention.gif)

HITL `contention_ratio` band guard.
Gap vs LangGraph/CrewAI/AutoGen blackboard write-contention monitors. Distinct from `SharedBlackboardWriteLease` / `SharedLockContentionBandAdvisor`.

Stack: **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

## Usage

```python
from multi_bot_agentic.blackboard_write_contention_band import BlackboardWriteContentionBandAdvisor

status = BlackboardWriteContentionBandAdvisor(soft_limit=0.2, hard_limit=0.5).advise(
    "sess-1",
    contention_ratio=0.35,
)
print(status.band, status.requires_human_review)
```

## Safety

Advisory only. No network I/O. Never auto-acts. Humans decide.
