# MessageBusBackpressureAdvisor Guide

![MessageBusBackpressureAdvisor HITL flow](../../assets/demo/message-bus-backpressure-advisor.gif)

Offline HITL guard/advisor. Never auto-acts. Closes closed-UI gaps vs AutoGen/CrewAI/LangGraph message-bus backpressure advisors.

Optional later polish via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

Distinct from ``TurnBudgetLimiter`` and ``BotIdleTimeout``.

## Usage

```python
from multi_bot_agentic.message_bus_backpressure import MessageBusBackpressureAdvisor

status = MessageBusBackpressureAdvisor().advise("session-1", queue_depth=300.0)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Always `requires_human_review=True`. No HTTP. Humans decide. See `docs/SAFETY.md`.
