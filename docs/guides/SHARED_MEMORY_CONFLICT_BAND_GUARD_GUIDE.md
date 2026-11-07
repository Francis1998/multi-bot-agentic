# SharedMemoryConflictBandGuard Guide

![SharedMemoryConflictBandGuard](../../assets/demo/shared-memory-conflict-band-guard.gif)

Offline HITL guard. Surfaces shared-memory version-skew conflicts. Closes
gaps vs AutoGen / CrewAI / LangGraph CRDT conflict bands.

Optional later polish via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

Distinct from `SharedMemoryQuotaGuard` and `SharedBlackboardWriteLease`.

## Usage

```python
from multi_bot_agentic.shared_memory_conflict_band import SharedMemoryConflictBandGuard

status = SharedMemoryConflictBandGuard().check("s1", key="plan", local_version=1, remote_version=4)
assert status.requires_human_review is True
print(status.band, status.version_skew)
```

## Safety

Always `requires_human_review=True`. No HTTP. Humans decide. See `SAFETY.md`.
