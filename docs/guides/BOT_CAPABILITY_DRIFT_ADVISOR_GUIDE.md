# BotCapabilityDriftAdvisor Guide

![BotCapabilityDriftAdvisor HITL flow](../../assets/demo/bot-capability-drift.gif)

Offline HITL guard/advisor. Never network I/O. Gap vs AutoGen/CrewAI/LangGraph bot capability-drift advisors.

Distinct from `StickyBotAffinityAdvisor` / `BotTurnFairnessAdvisor`.

Optional polish via **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

## Usage

```python
from multi_bot_agentic.bot_capability_drift import BotCapabilityDriftAdvisor

status = BotCapabilityDriftAdvisor().advise("s1", drift_ratio=0.1)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Always `requires_human_review=True`. Humans decide.
