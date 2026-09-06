# Typed Bot Handoff Guide

![Bot handoff demo](../../assets/demo/bot-handoff.gif)

Minimal multi-bot routing for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 crews.

## Why

Single-bot allowlists cannot express planner→writer style specialization. Frameworks
like CrewAI, AutoGen, and LangGraph provide rich handoff graphs; this repo adds a
thin, auditable `HANDOFF:bot_id:summary` directive without rewriting the runner.

## What This Adds

- `BotSpec` registry (`bot_id`, `name`, `allowed_tools`)
- Decision parsing for `HANDOFF:<bot_id>:<summary>`
- Runner switches `active_bot_id` and replaces the live tool allowlist
- Unknown bots are rejected (`fail`)

## Gap vs CrewAI / AutoGen / LangGraph

| Capability | multi-bot-agentic | CrewAI / AutoGen / LangGraph |
| --- | --- | --- |
| Handoff signal | `HANDOFF:bot_id:summary` text directive | Native agent/node edges |
| Tool isolation | Per-bot frozenset allowlist swap | Role tools / graph node tools |
| Orchestration | Additive ODA loop continuation | Dedicated crew/graph runtime |
| Audit | Event-log `action_result kind=handoff` | Framework-specific traces |

## Usage

```python
from multi_bot_agentic.bots import BotSpec
from multi_bot_agentic.runner import AgentRunner

bots = {
    "planner": BotSpec("planner", "Planner", frozenset({"checklist"})),
    "writer": BotSpec("writer", "Writer", frozenset({"echo"})),
}
runner = AgentRunner(..., bots=bots, active_bot_id="planner")
```

Model directive:

```text
HANDOFF:writer:draft the final answer
```

## Safety

- Handoffs are only accepted for bots present in the registry.
- After handoff, tools outside the destination bot allowlist are blocked.
- Step budgets, cancellation, and prompt bounds still apply.
