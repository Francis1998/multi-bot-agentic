# Checkpoint Resume Guide

![Checkpoint resume demo](../../assets/demo/checkpoint-resume.gif)

Durable Observe→Decide→Act checkpoints for runs on any provider (OpenAI, Claude Code, Gemini, Kimi, or `fake`).

## Why

A long agent run can be interrupted mid-loop: the process is killed, the host restarts, or the CLI crashes. Without a checkpoint, restarting means replaying every tool/LLM call from step 0.

## What This Adds

- `EventType.CHECKPOINT` events in the existing sqlite event log
- `save_checkpoint(...)` / `load_latest_checkpoint(run_id)`
- `AgentRunner.resume(run_id)` plus CLI `resume`

## Gap vs LangGraph Checkpointers

LangGraph ships thread-scoped checkpointers (MemorySaver, SqliteSaver, PostgresSaver) with graph-node cursors and channel values. This module is intentionally thinner:

| Capability | multi-bot-agentic | LangGraph |
| --- | --- | --- |
| Storage | Reuses event log rows | Dedicated checkpoint store |
| Granularity | Per-step observation snapshot | Per-node channel snapshot |
| API | `resume(run_id)` | `graph.invoke(..., thread_id=...)` |
| Dependencies | stdlib sqlite only | LangGraph checkpoint packages |

## Usage

```bash
multi-bot-agentic run --goal "Draft a launch plan" --provider fake --run-id run-1 --event-log /tmp/runs.sqlite
# Continues run-1 only if it was interrupted; a finished run returns its recorded outcome.
multi-bot-agentic resume --run-id run-1 --event-log /tmp/runs.sqlite --provider fake
```

Library API:

```python
from multi_bot_agentic.checkpoint import load_latest_checkpoint, save_checkpoint
from multi_bot_agentic.runner import AgentRunner

snapshot = load_latest_checkpoint(event_log, "run-1")
result = runner.resume("run-1")
```

## Which Runs Resume

`resume` continues only an **interrupted** run, meaning one whose log has no terminal event
(`run_completed`, `run_failed`, or `run_cancelled`). A **finished** run is final, because terminal
lifecycle states have no outgoing transitions. For a finished run, `resume` executes nothing and
appends no events. It returns the recorded outcome instead, so calling it again is safe (idempotent):
there are no repeated tool side effects, no extra provider spend, and no duplicate `run_completed`.

| Run in the event log | `resume` does | `RunResult.already_finished` | CLI `"resumed"` | CLI exit |
| --- | --- | --- | --- | --- |
| Interrupted: no terminal event (process killed, host restart) | Continues from the latest checkpoint | `False` | `true` | 0 if it then succeeds, else 2 |
| Succeeded (`run_completed`) | Returns the recorded answer; executes nothing | `True` | `false` | 0 |
| Failed (`run_failed`, e.g. a provider error) | Returns the recorded reason; executes nothing | `True` | `false` | 2 |
| Cancelled (`run_cancelled`) | Returns the recorded reason; executes nothing | `True` | `false` | 2 |

For a finished run the CLI also prints `note: run <id> already finished (<state>); nothing to resume`
on stderr, and stdout stays JSON. To retry a failed or cancelled run, start a new `run` with a new run
id. Removing the cancellation file does not reopen a cancelled run.

Real transcript (fake provider). The event count is unchanged after `resume`:

```text
$ multi-bot-agentic run --goal "Draft a launch plan" --provider fake --run-id run-1 --event-log runs.sqlite
{
  "run_id": "run-1",
  "state": "succeeded",
  "answer": "synthesized plan from 3 observations",
  "steps": 4,
  "event_log": "runs.sqlite"
}
$ multi-bot-agentic report --event-log runs.sqlite --run-id run-1 | grep event_count
      "event_count": 37,
$ multi-bot-agentic resume --run-id run-1 --event-log runs.sqlite --provider fake
note: run run-1 already finished (succeeded); nothing to resume
{
  "run_id": "run-1",
  "state": "succeeded",
  "answer": "synthesized plan from 3 observations",
  "steps": 4,
  "event_log": "runs.sqlite",
  "resumed": false
}
$ multi-bot-agentic report --event-log runs.sqlite --run-id run-1 | grep event_count
      "event_count": 37,
```

## Safety

- Checkpoints store observation text already accepted by the runner; they do not grant new tools.
- A finished run is never re-executed, so tools with side effects are not repeated by `resume`.
- `resume` does not lock a run. Do not resume the same interrupted run from two processes at once.
- Checkpoints record the active bot (`active_bot_id`) for multi-bot runs. `resume` restores that bot's
  tool scope, executes later `HANDOFF:` directives exactly like `run`, and raises `ValueError` if the
  checkpoint's bot is not registered on the resuming runner (fail closed instead of widening scope).
- Resume still enforces `SafetyPolicy` step budgets, tool allowlists, and cancellation files.
- Only the latest checkpoint for a `run_id` is loaded.
