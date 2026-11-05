# SupervisorHandoffLoopBandAdvisor Guide

![SupervisorHandoffLoopBandAdvisor](../../assets/demo/supervisor-handoff-loop.gif)

Offline helper.
Gap vs LangGraph/CrewAI/AutoGen supervisor handoff-loop monitors. Distinct from `AgentHandoffLoopBandAdvisor` / `HandoffSchemaDriftBandAdvisor`.

Stack: **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

## Usage

```python
from multi_bot_agentic.supervisor_handoff_loop_band import SupervisorHandoffLoopBandAdvisor

status = SupervisorHandoffLoopBandAdvisor().advise("session-1", loop_ratio=0.35)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Advisory only. No network I/O. Never auto-acts. Humans decide.
