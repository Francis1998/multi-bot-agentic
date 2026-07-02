# Use Case: Invalid step budgets should fail fast

**Issue:** #004
**Repository:** multi-bot-agentic

## Problem

The step budget (`max_steps`) bounds how many Observe → Decide → Act iterations a
run may take. It is the primary guard against runaway loops. When an operator
passes a nonsensical value — for example `--max-steps 0` — the misconfiguration
must surface immediately instead of being silently rewritten to a default. A
silent fallback hides operator error and produces a run whose bound is not the
one that was requested.

## How this agent solves it

`AppConfig.from_env` resolves the override explicitly (only falling back to the
`MULTIBOT_MAX_STEPS` environment variable or the built-in default when no value
is supplied) and rejects any resolved budget below `1` with a `ValueError`. This
closes a bug where `max_steps or <default>` treated the falsy value `0` as
"unset" while letting negative values pass through unchecked.

## Agentic design elements

| Component | Role |
|-----------|------|
| Safety layer | `SafetyPolicy.max_steps` bounds the loop; config validates it up front |
| Decision engine | Emits a terminal `finish` when the step budget is reached |
| State machine | Run lifecycle: `created → observing → deciding → acting → succeeded/failed/cancelled` |
| Event log | Records `RUN_FAILED` when a run exhausts its bound |

## LLM integration

Supports OpenAI-compatible APIs (GPT), Anthropic (Claude), Google (Gemini),
and Moonshot (Kimi) via the adapter registry. The step budget applies uniformly
across every provider.

## Try it

```bash
cp .env.example .env
pytest tests/test_config.py::test_app_config_rejects_non_positive_max_steps -q
```
