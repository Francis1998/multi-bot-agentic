# BlackboardStaleEntryAdvisor Guide

![BlackboardStaleEntryAdvisor HITL flow](../../assets/demo/blackboard-stale-entry-advisor.gif)

Offline HITL guard/advisor. Never auto-acts. Closes closed-UI gaps vs AutoGen/CrewAI/LangGraph blackboard stale-entry advisors.

Optional later polish via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

Distinct from ``SharedMemoryTtlEvictionAdvisor``.

## Usage

```python
from multi_bot_agentic.blackboard_stale_entry import BlackboardStaleEntryAdvisor

status = BlackboardStaleEntryAdvisor().advise("session-1", stale_age_seconds=900.0)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Always `requires_human_review=True`. No HTTP. Humans decide. See `docs/SAFETY.md`.
