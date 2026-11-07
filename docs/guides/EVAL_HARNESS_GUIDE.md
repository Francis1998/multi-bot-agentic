# Offline Evaluation Harness Guide

![Eval harness demo](../../assets/demo/eval-harness.gif)

Golden-path scoring for GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro agent loops.

## Why

Regressions in tool routing or DONE answers are hard to catch without replaying
a fixed Fake-LLM script. Hosted eval products add network and account overhead.

## What This Adds

- `multi_bot_agentic.eval.EvaluationHarness`
- JSON fixtures under `src/multi_bot_agentic/eval/fixtures/`
- Metrics: tool-sequence score + DONE answer score
- CLI: `multi-bot-agentic eval`

## Gap vs LangSmith / CrewAI Evals

| Capability | multi-bot-agentic | LangSmith / CrewAI |
| --- | --- | --- |
| Runtime | Offline Fake/scripted LLM | Hosted traces + datasets |
| Graders | Deterministic tool/DONE scores | LLM-as-judge, custom evaluators |
| UI | CLI JSON report | Web datasets / experiment UI |
| Dependencies | stdlib + local sqlite | Cloud project credentials |

## Usage

```bash
multi-bot-agentic eval
multi-bot-agentic eval --fixtures src/multi_bot_agentic/eval/fixtures
```

```python
from pathlib import Path
from multi_bot_agentic.eval import EvaluationHarness, default_fixture_dir, load_scenarios

report = EvaluationHarness(load_scenarios(default_fixture_dir())).run(
    root=Path.cwd(),
    event_log_dir=Path("data/eval-logs"),
)
assert report.pass_rate == 1.0
```

## Event Logs

Each scenario is logged to `<event-log-dir>/<scenario_id>.sqlite` (default `data/eval-logs`). Every execution
is a new run with a fresh run id, `<scenario_id>-<12 hex chars>`, and the report returns it as
`details.run_id`. Scores come only from that run's events. Earlier evaluations stay in the file as separate
runs, so re-running `eval` into the same directory, for example after you edit a fixture or the code, can't
reuse their tool calls. Replay the run that was scored:

```bash
multi-bot-agentic replay --event-log data/eval-logs/echo_then_done.sqlite \
  --run-id "<details.run_id from the eval output>" --format text
```

## Fixture Schema

```json
{
  "scenario_id": "checklist_happy_path",
  "goal": "Create an agent launch checklist",
  "scripted_responses": ["TOOL:checklist:...", "DONE: launch checklist ready"],
  "expected_tools": ["checklist"],
  "expected_answer": "launch checklist ready",
  "max_steps": 5
}
```

## Safety

Fixtures execute only allowlisted tools under `SafetyPolicy`. Scripted responses
cannot expand the tool allowlist or bypass step budgets.
