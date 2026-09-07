# Shared Blackboard Guide

![Shared blackboard demo](../../assets/demo/shared-blackboard.gif)

Bounded in-process key/value board for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 multi-bot crews.

## Why

Planner→writer handoffs need a place to stash short facts (outline, constraints, ids)
without stuffing every observation. Frameworks like CrewAI and AutoGen ship shared
memory objects; LangGraph exposes shared state channels. This module adds a thin,
stdlib-only board with explicit capacity caps.

## What This Adds

- `BlackboardEntry` (`key`, `value`, `writer_bot_id`, `revision`)
- `SharedBlackboard.put` / `get` / `delete` / `snapshot`
- Bounds: `max_keys` (default 64), `max_value_chars` (default 4000)

## Gap vs CrewAI / AutoGen / LangGraph

| Capability | multi-bot-agentic | CrewAI / AutoGen / LangGraph |
| --- | --- | --- |
| Storage | In-process dict | Shared memory / graph channels |
| Persistence | None (caller owns durability) | Often backed by stores/checkpointers |
| Bounds | Hard key/value caps | Framework-specific |
| Audit | Optional `writer_bot_id` + revision | Framework traces |

## Usage

```python
from multi_bot_agentic.blackboard import SharedBlackboard

board = SharedBlackboard(max_keys=32, max_value_chars=2000)
board.put("outline", "## Launch plan", writer_bot_id="planner")
entry = board.get("outline")
assert entry is not None
print(entry.revision, entry.value)
```

## Safety

- Values are opaque strings; the board does not grant tools or network access.
- Empty keys, oversize values, and capacity overflow raise `ValueError`.
- Overwriting an existing key does not consume an extra slot; revisions increment.
