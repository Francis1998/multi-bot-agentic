# Use Case: Tool failures should not crash the run

**Issue:** #003
**Repository:** multi-bot-agentic

## Problem

A tool adapter can return `ok=False` (missing file, path outside root, provider timeout).
If the runner treated that as a fatal error, the entire agent run would fail and the event
log would lose the partial trace.

## How this agent solves it

Failed tool results are recorded as observations with `source=tool:<name>`. The deterministic
decision engine routes back to the LLM via `tool.result-needs-synthesis`, giving the model
another turn to recover or finish with the error context.

## Agentic design elements

| Component | Role |
|-----------|------|
| Decision engine | Detects tool observations and schedules a follow-up LLM turn |
| State machine | Run lifecycle: `created → observing → deciding → acting → succeeded/failed/cancelled` |
| Event log | Persists `ACTION_RESULT` with `ok: false` for audit |
| Tool adapters | Return structured `ToolResult` instead of raising |
| Safety layer | Tool allowlist and root containment before execution |

## LLM integration

Supports OpenAI-compatible APIs (GPT), Anthropic (Claude), Google (Gemini),
and Moonshot (Kimi) via adapter registry. Model outputs are validated,
parsed into structured actions, and recorded in the event log.

## Try it

```bash
cp .env.example .env
pytest tests/test_runner.py::test_runner_recovers_after_tool_failure -q
```
