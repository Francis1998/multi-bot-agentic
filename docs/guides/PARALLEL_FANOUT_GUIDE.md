# Parallel Fan-Out Guide

![Parallel fan-out demo](../../assets/demo/parallel-fanout.gif)

Capped thread-pool fan-out for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 multi-bot batches.

## Why

Some goals split cleanly into independent sub-tasks (research angles, checklist
sections, provider A/B drafts). CrewAI/AutoGen crews and LangGraph parallel nodes
solve this with graph runtimes. This module keeps a stdlib `ThreadPoolExecutor`
helper that is easy to unit-test without calling `AgentRunner` or live LLMs.

## What This Adds

- `FanOutTask` / `FanOutResult` dataclasses
- `ParallelFanOut.run(tasks, worker)` with order-preserving results
- `merge_answers(...)` for joining successful answers
- Caps: `max_workers` (default 4), `max_tasks` (default 8)

## Gap vs CrewAI / AutoGen / LangGraph

| Capability | multi-bot-agentic | CrewAI / AutoGen / LangGraph |
| --- | --- | --- |
| Execution | `ThreadPoolExecutor` + callable worker | Crew/graph node concurrency |
| Ordering | Input-order results | Framework-specific |
| Failure model | Exceptions → `ok=False` | Node retries / handoffs |
| LLM coupling | None (inject your worker) | Usually bound to agents |

## Usage

```python
from multi_bot_agentic.fanout import FanOutResult, FanOutTask, ParallelFanOut


def worker(task: FanOutTask) -> FanOutResult:
    return FanOutResult(task_id=task.task_id, ok=True, answer=task.goal.upper())


fanout = ParallelFanOut(max_workers=2, max_tasks=4)
results = fanout.run(
    (
        FanOutTask("t1", "alpha", bot_id="researcher"),
        FanOutTask("t2", "beta", bot_id="researcher"),
    ),
    worker,
)
print(fanout.merge_answers(results))
```

## Safety

- Task count is hard-capped; oversized batches raise `ValueError`.
- Worker exceptions never escape `run`; they become failed `FanOutResult`s.
- This module does not grant tools, network, or provider credentials.
