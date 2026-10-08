# SharedMemoryPoisoningGuard Guide

![SharedMemoryPoisoningGuard HITL flow](../../assets/demo/shared-memory-poisoning.gif)

Offline HITL guard/advisor. Never network I/O. Gap vs AutoGen/CrewAI/LangGraph shared-memory poisoning guards.

Distinct from `SharedMemoryConflictBandAdvisor` / `ToolResultPoisoningGuard`.

Optional polish via **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

## Usage

```python
from multi_bot_agentic.shared_memory_poisoning import SharedMemoryPoisoningGuard

status = SharedMemoryPoisoningGuard().check("s1", poison_score=0.1)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Always `requires_human_review=True`. Humans decide.
