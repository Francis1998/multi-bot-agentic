# SharedKvLeaseExpiryBandAdvisor Guide

![SharedKvLeaseExpiryBandAdvisor](../../assets/demo/shared-kv-lease-expiry.gif)

Offline HITL band guard for `expiry_ratio`.
Gap vs LangGraph/CrewAI/AutoGen shared-KV lease-expiry monitors. Distinct from `BlackboardWriteLeaseAdvisor` / `SharedLockContentionBandAdvisor`.

Works with **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Usage

```python
from multi_bot_agentic.shared_kv_lease_expiry_band import SharedKvLeaseExpiryBandAdvisor

status = SharedKvLeaseExpiryBandAdvisor().advise("session-1", expiry_ratio=0.3)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Advisory only. No network I/O. Humans decide.
