# Use Case: A provider timeout should fail the run, not crash the process

**Issue:** #006
**Repository:** multi-bot-agentic

## Problem

`AgentRunner.run` wraps the Observe -> Decide -> Act loop in a handler that
catches `InvalidTransitionError`, `SafetyError`, `OSError`, `RuntimeError`, and
`ValueError`, converting any of them into a recorded `RUN_FAILED` result so the
event log always closes a run in a terminal state.

The Claude Code CLI provider executes a local subprocess with a timeout budget
(`subprocess.run(..., timeout=timeout_seconds)`). When the CLI exceeds that
budget, `subprocess.run` raises `subprocess.TimeoutExpired`. That exception is a
`SubprocessError`, which is **not** an `OSError`, `RuntimeError`, or
`ValueError`, so it slipped past the run loop's handler, propagated out of
`runner.run`, and crashed the CLI with an unhandled traceback — leaving the run
without a terminal `RUN_FAILED` event.

By contrast, the HTTP providers (OpenAI, Gemini, Kimi) use `urllib` whose
timeout surfaces as `TimeoutError` (an `OSError` subclass) and was already
handled, so the gap was specific to the subprocess-backed provider.

## How this agent solves it

The `ClaudeCodeCLIAdapter` catches `subprocess.TimeoutExpired` and re-raises it
as a `RuntimeError` — the same provider-failure contract it already uses for a
non-zero exit code. The runner's existing handler then records the run as
`RUN_FAILED` with the timeout reason, keeping the event log complete and
auditable.

## Agentic design elements

| Component | Role |
|-----------|------|
| LLM adapters | Surface provider failures as `RuntimeError`, never leak transport-specific exceptions |
| Runner loop | Records every provider failure as a terminal `RUN_FAILED` event |
| Safety layer | The per-provider timeout budget still bounds each call |
| Event log | Persists `RUN_FAILED` with the timeout reason for post-run audit |

## Try it

```bash
pytest tests/test_adapters.py::test_claude_code_adapter_maps_timeout_to_runtime_error -q
```
