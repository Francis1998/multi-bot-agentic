# Use Case: Non-deterministic agent loops hard to debug

**Issue:** #001
**Repository:** multi-bot-agentic

## Problem

Same input yields different tool order across runs.

## How this agent solves it

Observe-Decide-Act engine with seeded decisions and exported replay JSON.

## Agentic design elements

| Component | Role |
|-----------|------|
| Decision engine | Deterministic step selection with logged rationale |
| State machine | Run lifecycle: `pending → running → completed/failed/cancelled` |
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
