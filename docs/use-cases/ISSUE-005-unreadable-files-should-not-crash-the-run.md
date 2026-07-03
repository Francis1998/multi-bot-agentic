# Use Case: Unreadable files should not crash the run

**Issue:** #005
**Repository:** multi-bot-agentic

## Problem

`ISSUE-003` established that tool adapters must return a structured
`ToolResult` instead of raising, so a tool failure routes back to the model
rather than failing the whole run. The read-only file tool honored this for
*missing* paths and paths *outside the root*, but not for a file that exists
and passes `is_file()` yet cannot be decoded as UTF-8 text (for example a
binary artifact, or a file with an unexpected encoding).

In that case `read_text("utf-8")` raised `UnicodeDecodeError`, which escaped
the tool, propagated through the runner's `_act`, and was caught by the run
loop's broad handler — terminating the run in the `FAILED` state instead of
giving the model a turn to recover. A `PermissionError` (`OSError`) on a
readable-looking file had the same effect.

## How this agent solves it

The read is wrapped so any `OSError` or `UnicodeDecodeError` is converted into
`ToolResult(ok=False, ...)` with a descriptive message. The decision engine
then observes a `tool:` failure and applies the `tool.result-needs-synthesis`
rule, scheduling a follow-up LLM turn to recover or finish with error context.

## Agentic design elements

| Component | Role |
|-----------|------|
| Tool adapters | Return structured `ToolResult` for *all* read failures, never raise |
| Decision engine | Routes a failed tool observation back to the model |
| State machine | Run stays live (`acting → observing`) instead of `failed` |
| Event log | Persists `ACTION_RESULT` with `ok: false` for audit |
| Safety layer | Root containment still enforced before any read is attempted |

## Try it

```bash
pytest tests/test_tools.py::test_readonly_file_tool_returns_failure_for_non_utf8_file -q
pytest tests/test_runner.py::test_runner_recovers_after_unreadable_file -q
```
