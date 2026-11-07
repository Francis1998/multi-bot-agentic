# SharedMemoryTtlEvictionAdvisor Guide

![SharedMemoryTtlEvictionAdvisor](../../assets/demo/shared-memory-ttl-eviction-advisor.gif)

Closes AutoGen/CrewAI/LangGraph shared-memory TTL eviction advisors gaps.

Optional later polish via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

Distinct from `BlackboardEntryTtlEvictor` and `SharedMemoryQuotaGuard`.

## Usage

```python
from multi_bot_agentic.shared_memory_ttl_eviction import SharedMemoryTtlEvictionAdvisor

status = SharedMemoryTtlEvictionAdvisor().advise("session-1", expired_ratio=0.35)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Always `requires_human_review=True`. No HTTP. Humans decide.
