# SharedMemoryQuotaGuard Guide

![SharedMemoryQuotaGuard HITL flow](../../assets/demo/shared-memory-quota-guard.gif)

Offline HITL per-bot shared-blackboard write quota. Never performs network I/O.

Optional polish via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

Distinct from `SharedBlackboardWriteLease` and `BlackboardEntryTtlEvictor`.

## Usage

```python
from multi_bot_agentic.shared_memory_quota import SharedMemoryQuotaGuard

status = SharedMemoryQuotaGuard().check("sess-1", "researcher", writes_used=18, max_writes=20)
assert status.requires_human_review is True
print(status.band, status.remaining)
```
