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

Structured-output fields (see the [Structured Output Guide](STRUCTURED_OUTPUT_GUIDE.md#evaluation-fixtures)):
`output_schema` (an inline schema or a path relative to the fixture), `output_retries` (default `2`),
`expected_output` (any JSON value), and `expected_output_match` (`exact`, the default, or `subset`). The packaged
`structured_output_correction.json` scenario scripts one correction round.

Optional token and cost budgets (see the [Usage Limits Guide](USAGE_LIMITS_GUIDE.md#eval-budgets)):

| Field | Type | Meaning |
| --- | --- | --- |
| `max_total_tokens` | integer >= 0 | The run's total tokens must not exceed it |
| `max_cost_usd` | number >= 0 | The run's cost must be known and not exceed it |
| `model` | string | Model id the offline usage is priced as (default `fake`, $0), e.g. `gpt-6.2-sol` |

The packaged `usage_budget.json` scenario prices its scripted run as `gpt-6.2-sol` and sets both budgets.

## Scoring

- `tool_sequence_score` is the longest common prefix of the run's tool calls (`actual_tools`) and
  `expected_tools`, divided by the length of the longer of the two. It is `1.0` only when the run called exactly
  `expected_tools`, in order. Missing calls and extra calls both lower it: with `"expected_tools": ["echo"]`, a run
  that calls `["echo", "rot13"]` or `["echo", "echo"]` scores `0.5`. With `"expected_tools": []`, any call scores
  `0.0`. List every tool call the run should make, including repeated calls.
- `answer_score` is `1.0` when the DONE answer equals `expected_answer` (ignoring surrounding whitespace) and
  contains `expected_answer_contains`, checking only the ones that are set. With neither set, it is `1.0`.
- `output_score` is `1.0` when the scenario asserts no structured output. With `output_schema`, the run must end
  with a validated output; with `expected_output`, that output (or, without a schema, the JSON read from the
  answer) must match it exactly or as a subset. Otherwise it is `0.0`. The summary reports `mean_output_score`.
- A scenario passes when all three scores are `1.0`, the run succeeded, and every budget it sets holds (an unknown
  total fails its budget). Each scenario's `details` hold its `usage` and, with budgets, `budget_checks`; the summary
  adds `usage_totals` across scenarios. `eval` exits `2` when any scenario fails.

## Safety

Fixtures execute only allowlisted tools under `SafetyPolicy`. Scripted responses
cannot expand the tool allowlist or bypass step budgets.
