# MessageBusPoisonPillGuard Guide

![MessageBusPoisonPillGuard HITL flow](../../assets/demo/message-bus-poison-pill.gif)

Offline HITL guard. Never network I/O. Closes gaps vs AutoGen/CrewAI/LangGraph message-bus poison-pill guards.

Optional polish via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

Distinct from `MessageBusBackpressureAdvisor` / `SharedMemoryPoisoningGuard`.

## Usage

```python
from multi_bot_agentic.message_bus_poison_pill import MessageBusPoisonPillGuard

status = MessageBusPoisonPillGuard().check("s1", poison_score=0.1)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Always `requires_human_review=True`. No HTTP. Humans decide.
