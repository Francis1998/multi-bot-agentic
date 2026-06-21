# Use Case: Long-running tasks need cancellation

**Issue:** #002
**Repository:** multi-bot-agentic

## Problem

User cannot stop a runaway agent loop.

## How this agent solves it

Cancellation token checked each ODA step; state machine transitions to `cancelled`.

## Agentic design elements

| Component | Role |
|-----------|------|
| Decision engine | Deterministic step selection with logged rationale |
| State machine | Run lifecycle: `created → observing → deciding → acting → succeeded/failed/cancelled` |
| Event log | Durable SQLite/JSON audit trail for replay |
| Tool adapters | Pluggable integrations (HTTP, LLM, retrieval) |
| Safety layer | Timeouts, bounded scope, cancellation tokens |

## LLM integration

Supports OpenAI-compatible APIs (GPT), Anthropic (Claude), Google (Gemini),
and Moonshot (Kimi) via adapter registry. Model outputs are validated,
parsed into structured actions, and recorded in the event log.

## Try it

```bash
cp .env.example .env
# Set OPENAI_API_KEY / ANTHROPIC_API_KEY / GEMINI_API_KEY / KIMI_API_KEY
pytest tests/ -q
```
