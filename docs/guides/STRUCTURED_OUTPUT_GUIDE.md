# Structured Output Guide

**Typed, validated final answers.** `run --output-schema schema.json` makes the final answer of a run a JSON
document that must validate against a JSON Schema. An invalid answer is not the end of the run: the validation errors
go back to the model for a correction round, up to `--output-retries` rounds, and only then does the run stop in its
own state, `output_invalid`, with exit code 4. The schema is recorded in the run, so `resume` and `fork` enforce the
same contract, and `replay`, `report`, `history`, `trace`, and `eval` all show the validated output or the last
errors. `--output-file` hands the document to the next step of a pipeline.

![Structured output demo: a launch-plan schema, a fake-provider run that needs one correction round, the replayed validation events, the validated output file, a run without correction rounds that exits 4, a fork that rescues it, the Mermaid trace, and an eval scenario that asserts the output](../../assets/demo/structured-output.gif)

The GIF is a real session with the offline fake provider ([how it was recorded](#how-this-demo-was-recorded)).

## Contents

- [Why](#why)
- [Prerequisites](#prerequisites)
- [Quickstart](#quickstart)
- [How It Works](#how-it-works)
- [Supported Schema Keywords](#supported-schema-keywords)
- [Limits](#limits)
- [CLI Reference](#cli-reference)
- [Python API](#python-api)
- [Evaluation Fixtures](#evaluation-fixtures)
- [Worked Examples](#worked-examples)
- [Configuration](#configuration)
- [Interaction With Other Features](#interaction-with-other-features)
- [Event Reference](#event-reference)
- [Safety](#safety)
- [Limitations And Roadmap](#limitations-and-roadmap)
- [Troubleshooting](#troubleshooting)
- [FAQ](#faq)
- [How This Demo Was Recorded](#how-this-demo-was-recorded)
- [Related](#related)

## Why

A run used to end with free text: `DONE: <anything>`. That is fine for a person reading a report, but a pipeline
step that consumes the result (a ticket creator, a deploy gate, a spreadsheet) needs a document with a known shape,
and it needs to know when it did not get one. Popular agent frameworks make this a core feature:

| Project | How it exposes typed output | What happens on an invalid answer |
| --- | --- | --- |
| [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/agents/#output-types) | `Agent(output_type=CalendarEvent)` (any Pydantic-compatible type) uses the provider's structured outputs | An answer that does not validate raises `ModelBehaviorError` |
| [Pydantic AI](https://ai.pydantic.dev/output/) | `Agent(output_type=...)` with tool, native (`NativeOutput`), or prompted (`PromptedOutput`) output modes, plus `@agent.output_validator` | A validation error or `ModelRetry` is sent back to the model, up to the agent's output retries |
| [Instructor](https://github.com/567-labs/instructor) | `client.chat.completions.create(response_model=User, max_retries=3)` | Pydantic validation errors are sent back and the model is re-asked, up to `max_retries` |
| [CrewAI](https://docs.crewai.com/concepts/tasks) | `Task(output_json=Model)` or `Task(output_pydantic=Model)`, plus task `guardrail`s | A guardrail can reject the output and retry the task, up to `guardrail_max_retries` |
| **multi-bot-agentic** (this guide) | `run --output-schema schema.json` (a JSON Schema file, any provider) | `output_validation_failed` event, then a correction round with the errors, up to `--output-retries`; then the `output_invalid` state and exit code 4 |

Before this feature the repository had schemas only for **tools**: MCP `inputSchema`/`outputSchema` and the
`ToolOutputSchemaGate`, which checks required keys of a tool result. Nothing let a run promise a machine-readable
final answer, correct an invalid one, record the validated document, or assert it in an offline evaluation.

What this adds, in the repository's own terms:

- **A contract recorded in the run.** The schema, its SHA-256, its source path, and the correction-round budget go
  into the `run_created` event, so the contract survives the process: `resume` enforces it, and a fork inherits it
  or records a new one in its lineage.
- **Deterministic correction rounds.** The decision engine gets one more rule, `output.invalid-needs-correction`:
  after an invalid answer, the next step is a model call that sees the validation errors as an observation. Every
  round is an ordinary, replayable step with a rationale trace.
- **Explicit states.** The state machine gets `validating` (an answer is being checked) and the terminal
  `output_invalid` (no round or step is left). An invalid output never looks like success.
- **A strict, dependency-free validator.** A documented JSON Schema subset with precise error paths such as
  `$.items[2].price: expected number, got string`. A keyword the validator does not implement is refused when the
  schema is loaded, so no constraint is ever silently ignored.

## Prerequisites

- The repository installed (`python -m pip install -e ".[dev]"`), Python 3.10 or newer. No extra dependency.
- A JSON Schema file. [`examples/structured-output/launch-plan.schema.json`](../../examples/structured-output/launch-plan.schema.json)
  is used below. Schemas exported by Pydantic (`Model.model_json_schema()`) work when they use only the
  [supported keywords](#supported-schema-keywords); remove `format` first (see [FAQ](#faq)).
- Any provider. The examples use the offline fake provider, which needs no key; with GPT-6.2 Sol, Claude Opus 5.5,
  Gemini 4 Neon, or Kimi K3.1 Pro the schema is part of every prompt (see [How It Works](#how-it-works)).

## Quickstart

```bash
# 1. Run with an output contract. The fake provider's first answer is plain text, so one correction round runs.
multi-bot-agentic run --goal "Plan the agent launch" --provider fake --event-log data/runs.sqlite --run-id plan \
  --output-schema examples/structured-output/launch-plan.schema.json --output-file data/plan.json
echo "exit code: $?"     # 0: the output validated and data/plan.json holds it

# 2. See the correction round: the failed check, the correction decision, and the final output.
multi-bot-agentic replay --event-log data/runs.sqlite --run-id plan --format text | grep -E "validating|correction"

# 3. Summarize it.
multi-bot-agentic report --event-log data/runs.sqlite --run-id plan | jq ".runs[0].output | {valid, attempts}"

# 4. Without correction rounds the same run stops in output_invalid and exits 4; nothing is written to --output-file.
multi-bot-agentic run --goal "Plan the agent launch" --provider fake --event-log data/runs.sqlite --run-id strict \
  --output-schema examples/structured-output/launch-plan.schema.json --output-retries 0
echo "exit code: $?"     # 4

# 5. Retry it from its last good step with more correction rounds; the fork keeps the schema.
multi-bot-agentic fork --event-log data/runs.sqlite --run-id strict --at-step 3 --new-run-id strict-retry \
  --output-retries 1 --provider fake
```

With a real model, for example GPT-6.2 Sol, replace `--provider fake` with `--provider openai` after
`export OPENAI_API_KEY=...`; the model sees the schema in its prompt and usually answers with valid JSON first time.

## How It Works

```text
run --output-schema S      -> schema checked (every keyword, size, refs, patterns) before anything runs
run_created                -> {output_contract: {schema, schema_sha256, source, retries}}
every model request        -> ModelRequest.output_schema = S; the prompt gains a "Final answer contract" section
DONE:<answer>              -> decision finish -> state validating -> extract the JSON document -> validate
  valid                    -> final_output {output, attempt, source, output_sha256, bytes} -> succeeded (exit 0)
  invalid, a round is left -> output_validation_failed {attempt, errors, retry: true} -> checkpoint
                              -> output:validation observation -> observing
                              -> decision call_llm (output.invalid-needs-correction) -> the model corrects it
  invalid, nothing left    -> output_validation_failed {retry: false, stop} -> output_invalid + run_failed (exit 4)
```

**Finding the JSON document.** The answer is the text after `DONE:` (or, on the last step of the budget, the latest
observation). The rules, in order, are deterministic:

1. The whole answer, without surrounding whitespace, is a JSON document (object, array, string, number, `true`,
   `false`, or `null`). Source `answer`.
2. Otherwise, exactly one fenced block whose info string is `json` (in any case), with the fences on their own
   lines, holds the document. Source `json_block`. Prose around the block is ignored; other fenced blocks (for
   example `python`) are ignored too. **Two or more `json` blocks are an error**, never a guess.
3. Otherwise there is no document. An answer that starts with `{` or `[` reports its JSON syntax error (with line
   and column); any other answer reports `no JSON document found`.

JSON is parsed strictly: `NaN`, `Infinity`, and duplicate object keys are errors. The document must also fit 64 KiB
of compact JSON and 64 levels of nesting before it is validated.

**A correction round** is one model call plus the check of its answer, so it needs two steps of `--max-steps`.
The model sees an `output:validation` observation that lists the errors (never the schema again; the schema is
already in every prompt):

```text
OUTPUT_INVALID: final answer attempt 1 of 3 failed validation against the output schema (sha256 f4194116eeba):
- $: no JSON document found; reply with only the JSON document, or put it in one ```json fenced block
Reply with DONE: followed by only the corrected JSON document.
```

A run stops in `output_invalid` when the answer of attempt `retries + 1` is invalid (`stop: retries_exhausted`), or
earlier when fewer than two steps are left for another round (`stop: step_budget`).

**What every provider sees.** `ModelRequest.output_schema` carries the schema, and the OpenAI-compatible (GPT-6.2,
Kimi K3.1), Gemini 4, and Claude Code adapters append a section to the prompt:

```text
Final answer contract: when finished, reply DONE: followed by only a JSON document (or exactly one ```json fenced
block) that validates against this JSON Schema:
{"$defs":{"step":{"maxLength":120,"minLength":5,"type":"string"}},"$schema":"https://json-schema.org/...", ...}
```

Prompts of runs without a schema are byte-for-byte unchanged. For runs with a schema, the provider output bound
rises from 2,000 to 16,000 characters, so a JSON document is not cut off. Validation is always local: the answer of
any provider, real or fake, goes through the same checks.

**The fake provider** answers as before, so its first final answer is plain text, like a model that ignored the
format instruction. After a correction observation it answers with a JSON document built from the schema, the goal,
and the lines of the latest tool result. Every fake run with a schema therefore shows exactly one correction round,
which keeps demos and tests deterministic.

## Supported Schema Keywords

The validator implements this subset of JSON Schema 2020-12. Every other keyword is **refused when the schema is
loaded** (`unsupported keyword "format"; it would not be enforced, so the schema is refused`), so a schema never
appears to enforce a constraint that is not checked.

| Keyword | Applies to | Rule (error message) |
| --- | --- | --- |
| `type` | any | A type name or an array of names: `object`, `array`, `string`, `number`, `integer` (`2.0` counts), `boolean`, `null`. `true` is not a number (`expected string or null, got integer`) |
| `enum` | any | JSON equality with one of a non-empty array: `1` equals `1.0`, `true` is not `1` (`expected one of ["low", "high"], got "urgent"`) |
| `const` | any | JSON equality (`expected 3, got 4`) |
| `properties` | object | Each named property that is present validates against its schema |
| `required` | object | Unique property names (`$.title: required property is missing`) |
| `additionalProperties` | object | `false` refuses other properties (`$.x: additional property is not allowed (allowed: a, b)`); a schema validates them |
| `items` | array | One schema for every item (`$[1]: expected number, got string`); an array of schemas is refused |
| `minItems`, `maxItems` | array | Item counts (`expected at least 3 items, got 1`) |
| `uniqueItems` | array | `true`: no two items are JSON-equal (`items must be unique, but items 0 and 2 are equal`) |
| `minLength`, `maxLength` | string | Length in Unicode code points (`expected at least 3 characters, got 2`) |
| `pattern` | string | Python `re` search, not a full match: anchor with `^...$` (`does not match pattern "^[A-Z]{3}$"`); see [Limits](#limits) |
| `minimum`, `maximum` | number | Inclusive bounds (`expected a number >= 1, got 0`) |
| `exclusiveMinimum`, `exclusiveMaximum` | number | Exclusive bounds, numbers only (the boolean draft-04 form is refused) |
| `allOf` | any | Every schema of a non-empty array |
| `anyOf` | any | At least one schema (`does not match any of the 2 anyOf alternatives; closest is alternative 0: ...`) |
| `oneOf` | any | Exactly one schema (`matches 2 oneOf alternatives (0, 1); expected exactly one`) |
| `$ref` | any | A JSON pointer inside the schema: `#`, `#/$defs/name`, `#/definitions/name`, `#/properties/a`. Applied together with sibling keywords (2020-12). Recursive schemas work; a cycle that never reaches a property or item is refused |
| `$defs`, `definitions` | - | Containers for referenced schemas (also checked) |
| `$schema`, `$comment`, `title`, `description`, `default`, `examples`, `deprecated`, `readOnly`, `writeOnly` | - | Annotations: accepted, never enforced (as in JSON Schema) |

Boolean schemas are supported anywhere: `true` accepts everything, `false` nothing (`no value is allowed here`).

Error paths name the offending value: `$` is the document, `$.items[2].price` a nested value, and
`$["odd key"]` a key that is not an identifier. Schema errors name a JSON pointer into the schema, for example
`schema #/properties/when: unsupported keyword "format"`. At most 20 errors are listed per answer, plus a
`(N more errors not shown)` line, and every error is at most 300 characters.

## Limits

| Limit | Value | When exceeded |
| --- | --- | --- |
| Schema file size | 256 KiB | `output schema <path> is N bytes; the limit is 262144` |
| Compact schema size | 64 KiB | `the output schema is N bytes in compact form; the limit is 65536` |
| Schema nesting | 32 levels | `schema #/...: nesting exceeds 32 levels` |
| Subschemas | 2,000 | `the schema has more than 2000 subschemas` |
| `pattern` length | 256 characters | `the pattern is N characters long; the limit is 256` |
| `pattern` shapes | no backreferences, no repeated group whose content varies in length | `the pattern repeats a group whose content varies in length (such as (a+)+ or (a\|ab)*)...` |
| String checked by `pattern` | 4,096 characters | a validation error: `is N characters long, too long to check against pattern ...` |
| Answer document | 64 KiB compact JSON, 64 levels | a validation error, so a correction round follows |
| Provider output (runs with a schema) | 16,000 characters | longer answers are cut off by the adapter (and then fail as invalid JSON) |
| `--output-retries` | 0-10 (default 2) | argparse error, exit code 2 |

## CLI Reference

### Exit codes (`run`, `fork`, `resume`)

| Code | Meaning |
| --- | --- |
| `0` | Succeeded. With a schema: the output validated (and `--output-file` was written) |
| `2` | Failed, cancelled, or refused before running (bad flags, unreadable or unsupported schema, unknown run), or `--output-file` could not be written |
| `3` | Paused awaiting human approval ([HITL interrupts](HITL_INTERRUPTS_GUIDE.md)) |
| `4` | `output_invalid`: no answer validated within the correction rounds or the step budget |
| `75` | Another process is continuing the run; nothing was written ([HITL interrupts](HITL_INTERRUPTS_GUIDE.md)) |

### `run --output-schema PATH [--output-retries N] [--output-file PATH]`

- `--output-schema PATH`: the JSON Schema file. It is read and checked before MCP servers start or the event log
  is opened, so a schema error writes nothing.
- `--output-retries N`: correction rounds after the first invalid answer, `0` to `10`, default `2` (so at most three
  answers are checked). It needs `--output-schema`.
- `--output-file PATH`: where the validated output is written when the run succeeds: indented JSON with sorted
  keys, written to a temporary file next to `PATH` and renamed over it. It is never written for a failed run. It
  needs `--output-schema`, and `PATH` must not be a directory.

The printed result gains `output` (the validated document) and `output_attempts` (which answer validated) on
success, `output_errors` (the errors of the last answer) for `output_invalid`, and `output_file` when the file was
written:

```json
{"run_id": "demo", "state": "succeeded", "answer": "{\"title\": ...}", "steps": 6, "event_log": "demo-output/output.sqlite",
 "output": {"title": "Plan the agent launch", "steps": ["..."], "risk": "low", "owner_count": 5},
 "output_attempts": 2, "output_file": "demo-output/plan.json"}
```

### `resume --output-file PATH`

`resume` enforces the contract recorded when the run started (there is no `--output-schema` on `resume`) and counts
the failed answers the run already used. `--output-file` writes the validated output when the resumed run succeeds,
and also re-exports the recorded output of a run that already finished. A run without a schema is refused:
`error: run plain has no output schema, so --output-file has nothing to write`.

### `fork --output-schema PATH --output-retries N --output-file PATH`

A fork keeps the source run's contract by default. `--output-schema` replaces the schema and `--output-retries` the
budget; each change is recorded under `overrides` in the fork's `run_forked` event (`output_schema` with the new
digest and source, `output_retries`), and the event always carries the fork's whole contract. Failed answers
inherited from the source count against the fork's rounds only when the schema is unchanged.
`fork --dry-run` prints the fork's `output_contract` (digest, source, retries) without the schema body.

### Errors (exit code 2, nothing is written)

| Message | Cause |
| --- | --- |
| `error: --output-file needs --output-schema PATH` | `--output-file` (or `--output-retries`) on a `run` without a schema |
| `error: cannot read output schema s.json: No such file or directory` | The schema file is missing or unreadable |
| `error: output schema s.json is not valid JSON: duplicate object key "type"` | The file is not strict JSON |
| `error: output schema s.json: schema #/properties/when: unsupported keyword "format"; ...` | A keyword outside the [supported subset](#supported-schema-keywords) |
| `error: --output-file out is a directory; name a file` | `--output-file` names a directory |
| `error: run plain has no output schema, so --output-file needs --output-schema PATH` | `fork --output-file` of a run without a schema |
| `error: run plain has no output schema; give the fork one (CLI: --output-schema PATH)` | `fork --output-retries` of a run without a schema |

## Python API

```python
from pathlib import Path

from multi_bot_agentic.event_log import SQLiteEventLog
from multi_bot_agentic.llm.fake import FakeLLMAdapter
from multi_bot_agentic.runner import AgentRunner, build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.structured_output import OutputContract, OutputSchema, check_output

schema = OutputSchema.load(Path("examples/structured-output/launch-plan.schema.json"))
tools = build_default_tools(root=Path.cwd())
runner = AgentRunner(
    provider=FakeLLMAdapter(),
    event_log=SQLiteEventLog(Path("data/runs.sqlite")),
    tools=tools,
    safety_policy=SafetyPolicy(max_steps=6, allowed_tools=frozenset(tools)),
)
result = runner.run("Plan the agent launch", output_contract=OutputContract(schema=schema, retries=2))
print(result.state.value, result.output.value if result.output else result.output_errors)

# The validator on its own: errors with paths, never an exception for any answer text.
print(check_output('{"title": "x"}', schema).errors)
```

- `OutputSchema.load(path)` / `OutputSchema.from_value(value)` check a schema and raise `SchemaError` (a
  `ValueError`) with the same messages as the CLI; `schema.validate(value)` returns the error tuple.
- `check_output(answer, schema)` returns an `OutputCheck` (`valid`, `value`, `errors`, `source`, `output_bytes`);
  `extract_json(answer)` applies the [extraction rules](#how-it-works) alone.
- `AgentRunner.run(goal, run_id=None, *, output_contract=None)`, `resume(run_id)` (reads the contract from the log),
  and `fork(..., output_schema=None, output_retries=None)`. `RunResult.output` is a `FinalOutput` (`value`,
  `attempt`, `source`, `output_sha256`, `output_bytes`, `schema_sha256`) and `RunResult.output_errors` the last
  errors; `RunState.VALIDATING` and `RunState.OUTPUT_INVALID` are the new states.

## Evaluation Fixtures

`eval` fixtures can assert structured outputs. The packaged
[`structured_output_correction.json`](../../src/multi_bot_agentic/eval/fixtures/structured_output_correction.json)
scenario scripts a plain-text answer and then a JSON one:

```json
{
  "scenario_id": "structured_output_correction",
  "goal": "Summarize the agent launch checklist as JSON",
  "scripted_responses": [
    "TOOL:checklist:agent launch",
    "DONE: the launch checklist has 5 items",
    "DONE: {\"title\": \"Agent launch\", \"item_count\": 5, \"ready\": true}"
  ],
  "expected_tools": ["checklist"],
  "output_schema": {"type": "object", "required": ["title", "item_count", "ready"], "additionalProperties": false,
                    "properties": {"title": {"type": "string", "minLength": 3},
                                   "item_count": {"type": "integer", "minimum": 1}, "ready": {"type": "boolean"}}},
  "expected_output": {"item_count": 5, "ready": true},
  "expected_output_match": "subset",
  "max_steps": 6
}
```

| Field | Default | Meaning |
| --- | --- | --- |
| `output_schema` | none | An inline schema, or a path relative to the fixture file. The run must end with a validated output |
| `output_retries` | `2` | Correction rounds of the run |
| `expected_output` | none | The expected JSON value. Without `output_schema` it is compared with the JSON read from the answer by the same extraction rules |
| `expected_output_match` | `exact` | `exact`: JSON equality (`1` equals `1.0`, key order ignored). `subset`: every expected object key must be present with a matching value, arrays must have the same length and match item by item, other values must be equal |

Each scenario gets an `output_score` (`1.0` when nothing is asserted, or when the output exists and matches; `0.0`
otherwise), and a scenario passes only with `output_score` 1.0. The summary adds `mean_output_score`, each scenario
its `actual_output`, and `details` gains `output_attempts` or `output_errors`.

## Worked Examples

These outputs were captured from `demo-output/output.sqlite` right after the [demo](#how-this-demo-was-recorded)
(the `demo` and `strict` runs are the ones in the GIF).

### The correction round, event by event

```bash
multi-bot-agentic replay --event-log demo-output/output.sqlite --run-id demo --event-type output_validation_failed | jq -c .payload
```

```json
{"attempt":1,"errors":["$: no JSON document found; reply with only the JSON document, or put it in one ```json fenced block"],"max_attempts":3,"retry":true,"schema_sha256":"f4194116eeba052b795176e40f99e060cc4caecf04ab2499fe227e896bd2b7ba"}
```

```bash
multi-bot-agentic replay --event-log demo-output/output.sqlite --run-id demo --event-type final_output | jq -c .payload
```

```json
{"attempt":2,"bytes":300,"output":{"owner_count":5,"risk":"low","steps":["Define scope for Plan the agent launch","Confirm safety policy and tool allowlist","Run fake-provider replay before live providers","Review rationale traces for every decision","Archive the sqlite event log for post-run audit"],"title":"Plan the agent launch"},"output_sha256":"3cc22aed3acdedc6e9ede3ebd8fbcce19d33df1163c7fd22936206cde68e0d62","schema_sha256":"f4194116eeba052b795176e40f99e060cc4caecf04ab2499fe227e896bd2b7ba","source":"answer"}
```

### `report` and `history` of a run that ended in `output_invalid`

```bash
multi-bot-agentic report --event-log demo-output/output.sqlite --run-id strict | jq '.runs[0].output'
```

```json
{
  "schema_sha256": "f4194116eeba052b795176e40f99e060cc4caecf04ab2499fe227e896bd2b7ba",
  "schema_source": "examples/structured-output/launch-plan.schema.json",
  "retries": 0,
  "attempts": 1,
  "valid": false,
  "errors": [
    "$: no JSON document found; reply with only the JSON document, or put it in one ```json fenced block"
  ]
}
```

```text
$ multi-bot-agentic history --event-log demo-output/output.sqlite --run-id strict
run strict: output_invalid after 4 steps (provider fake)
goal: Plan the agent launch
step  bot  action     target     rule                         outcome         fork
   0  -    start      -          -                            -               yes
   1  -    call_llm   fake       observe.no-model-output      TOOL checklist  yes
   2  -    call_tool  checklist  model.requested-tool         checklist ok    yes
   3  -    call_llm   fake       tool.result-needs-synthesis  DONE            yes
   4  -    finish     -          model.done-or-budget         output_invalid  no
forkable steps: 0, 1, 2, 3
```

In the `demo` run, step 4 has the outcome `output invalid` (a correction round followed) and stays forkable.

### A fork with a stricter schema, and the step budget

Fork the `demo` run after step 5 (its corrected answer, before the check) with a schema that allows at most three
owners. The recorded answer is checked against the new schema without calling the model:

```bash
jq '.properties.owner_count.maximum = 3' examples/structured-output/launch-plan.schema.json > demo-output/small-team.schema.json
multi-bot-agentic fork --event-log demo-output/output.sqlite --run-id demo --at-step 5 --new-run-id small-team \
  --output-schema demo-output/small-team.schema.json --dry-run | jq -c '{fork_step, remaining_steps, overrides, next_decision}'
```

```json
{"fork_step":5,"remaining_steps":1,"overrides":{"output_schema":{"schema_sha256":"3cd60768e33f4b054cf86535bdba16ee49278db9b81604c36b38e8dead5d8087","source":"demo-output/small-team.schema.json"}},"next_decision":{"action":"finish","target":null,"rule_id":"model.done-or-budget"}}
```

With one step left there is no room for a correction round, so the fork stops in `output_invalid` (exit 4):

```text
note: forked run demo after step 5 into small-team (50 events inherited; new output_schema)
note: run small-team ended in output_invalid; its answers and validation errors: replay --event-log demo-output/output.sqlite --run-id small-team --event-type output_validation_failed
{
  "run_id": "small-team",
  "parent_run_id": "demo",
  "fork_step": 5,
  "state": "output_invalid",
  "answer": "the final answer failed output validation and no steps are left for a correction round (raise --max-steps)",
  "steps": 6,
  "event_log": "demo-output/output.sqlite",
  "output_errors": [
    "$.owner_count: expected a number <= 3, got 5"
  ]
}
```

With `--max-steps 8` the fork has room for a round, and the corrected answer validates:

```bash
multi-bot-agentic fork --event-log demo-output/output.sqlite --run-id demo --at-step 5 --new-run-id small-team2 \
  --output-schema demo-output/small-team.schema.json --provider fake --max-steps 8 | jq -c '{state, steps, output_attempts, owner_count: .output.owner_count}'
```

```json
{"state":"succeeded","steps":8,"output_attempts":2,"owner_count":3}
```

The fork's `replay` also lists the inherited `output_validation_failed` event of the source; it was recorded under
the old schema, so it does not count against the fork's rounds.

## Configuration

Structured output is configured per run with the flags above; there are no environment variables. The schema is
recorded in the run, so nothing needs to be repeated for `resume`. `--max-steps` (or `MULTIBOT_MAX_STEPS`) must
leave two steps per correction round you want to allow. See [Configuration](../CONFIGURATION.md#structured-output).

## Interaction With Other Features

- **Checkpoint & resume.** A correction round ends with a checkpoint, so a run that dies during the corrected model
  call resumes from the errors; `resume` enforces the recorded contract and continues its attempt count.
- **Time-travel forks.** Forks inherit the contract (and, with the same schema, the failed answers), or take a new
  one with `--output-schema` / `--output-retries`. A step that ended a run in `output_invalid` is not forkable;
  the steps before it are, including steps that were followed by a correction round.
- **Human-in-the-loop interrupts.** A gated tool call pauses the run as usual (exit 3); after `approve` and
  `resume`, the final answer is still validated. The two exit codes never overlap.
- **Bot handoffs and MCP tools.** The contract belongs to the run, not to a bot: every bot's model calls see the same
  schema, and tool results (including MCP results) are observations the final answer can use.
- **Trace export.** `trace` adds a `multi_bot_agentic.output.validation` span event per checked answer (`valid`,
  `attempt`, `error_count`, `retry`, `bytes`; the errors only with `--include-content`, redacted) and root span
  attributes `multi_bot_agentic.output.schema_sha256`, `.attempts`, and `.valid`. An `output_invalid` run's root span
  has status error with `error.type` `output_invalid`; Mermaid diagrams show `output invalid (attempt 1, 1 error)` and
  `output valid (attempt 2)` notes.
- **Replay and report.** `replay --format text` shows `attempt=1/3 errors=1 retry=true first="..."` and
  `attempt=2 source=answer bytes=300 sha256=...`; `report` adds an `output` object per run with a schema.

## Event Reference

| Event | State | Payload |
| --- | --- | --- |
| `run_created` | `created` | `output_contract`: `schema`, `schema_sha256`, `source`, `retries` (only for runs with a schema) |
| `run_forked` | `created` | `output_contract` of the fork; `overrides.output_schema` (`schema_sha256`, `source`) and `overrides.output_retries` when changed |
| `output_validation_failed` | `validating` | `attempt`, `max_attempts`, `errors`, `schema_sha256`, `retry`, and `stop` (`retries_exhausted` or `step_budget`) when `retry` is false |
| `final_output` | `validating` | `output`, `attempt`, `source` (`answer` or `json_block`), `output_sha256`, `bytes`, `schema_sha256` |
| `observation` | `observing` | source `output:validation`: the correction text, with `attempt` and `schema_sha256` metadata |
| `run_failed` | `output_invalid` | `reason` (never quotes the answer) and `steps` |

## Safety

- A schema is data. Nothing in it is executed, imported, or fetched; `$ref` resolves only inside the schema.
- No silent gaps: an unsupported keyword is an error when the schema is loaded, never an ignored constraint.
- Bounded inputs: schema size, nesting, and subschema count; strict, bounded answer documents; at most 20 errors of
  at most 300 characters per answer.
- `pattern` runs on Python's backtracking `re` engine, which has no timeout. Backreferences and repeated groups
  whose content varies in length are refused, patterns are at most 256 characters, and strings over 4,096
  characters are not matched. Several adjacent overlapping quantifiers can still be slow on long strings, so treat
  schemas as trusted operator input: never load one from an untrusted source.
- Validation errors can quote short previews of the answer, so they are content. They stay in the event log;
  `trace` exports them only with `--include-content`, redacted, and the `run_failed` reason never quotes the answer.
- The correction observation repeats only the errors, never the schema, so a large schema is not sent twice.
- `--output-file` is written atomically, only for a validated output, and never to a directory.

See also [Safety](../SAFETY.md#structured-output-schemas).

## Limitations And Roadmap

- **Provider-native structured output is not used.** OpenAI Responses `text.format` / Chat Completions
  `response_format`, and Gemini `responseSchema` / `responseMimeType`, force *every* model turn to be JSON, while
  this engine reads `TOOL:`, `HANDOFF:`, and `DONE:` directives from text turns. The schema is therefore sent in the
  prompt to every provider, and validation is always local. A native mode for the final turn only is on the roadmap.
- **Keyword subset.** Not supported yet (refused when loading): `format`, `not`, `if`/`then`/`else`,
  `prefixItems`/tuple `items`, `contains`, `patternProperties`, `propertyNames`, `dependentRequired`,
  `dependentSchemas`, `minProperties`/`maxProperties`, `multipleOf`, `unevaluatedProperties`/`unevaluatedItems`,
  `$id`, `$anchor`, `$dynamicRef`, and remote `$ref`.
- **`pattern` dialect.** Python `re` syntax, which differs from ECMA-262 in places (for example `\d` matches
  non-ASCII digits, and lookbehind rules differ). The safety check is conservative and also refuses some safe
  patterns, such as `^[a-z]+(-[a-z]+)*$` (rewrite it as `^[a-z][a-z-]*$` or use `enum`).
- **One contract per run.** A fork can replace a schema but not drop it; start a new run for free text.
- **No partial validation while streaming**, and no Pydantic-model input: export the schema with
  `model_json_schema()` and validate the result with the model if you need Python objects.
- **The fake provider's corrected document** follows `type`, bounds, `enum`/`const`, `$ref`, and the first `anyOf`
  member, but not `pattern`; for elaborate schemas, script answers with an eval fixture instead.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `unsupported keyword "format"` | Remove `format` (or replace it with a `pattern`); see the [supported keywords](#supported-schema-keywords) |
| `the pattern repeats a group whose content varies in length` | Rewrite the pattern without a repeated variable-length group, or use `enum` |
| The run ends in `output_invalid` with `stop: step_budget` | Raise `--max-steps`: each correction round needs two steps |
| `no JSON document found` on every attempt | The model answers prose. Ask for JSON in the goal too, or use `--output-retries 3` |
| `the answer has 2 ```json blocks` | The model returned alternatives; the correction round asks for exactly one |
| `$.x: additional property is not allowed (allowed: ...)` | The model invented a field; the error lists the allowed names, so the next round usually fixes it |
| `resume` fails with `does not match its sha256 digest` | The recorded schema was edited in the event log; fork the run with `--output-schema` instead of editing it |
| `--output-file` was not written | It is written only for a validated output; check the exit code (4 means `output_invalid`) |

## FAQ

**Can I use a Pydantic model?** Export its schema with `Model.model_json_schema()`, write it to a file, and remove
keywords outside the subset (most often `format` for dates, emails, and URLs). Validate the written output with the
model afterwards if you need a Python object.

**Is `1.0` an integer? Is `true` a number?** `1.0` is an integer, as in JSON Schema; `true` is never a number, and
`enum: [1]` does not accept `true`.

**Why is `pattern` a search?** That is the JSON Schema rule: `"pattern": "[0-9]"` accepts `a1b`. Anchor with
`^...$` for a full match.

**Does validation call the model?** No. Validation is local and deterministic; only a correction round calls the
model, as an ordinary step of the run.

**What does `output_attempts` count?** Which answer validated: `1` is the first answer checked against this
schema; inherited answers of a fork with the same schema count too.

**Why does every fake run need a correction round?** The fake provider's first answer is the plain text it always
returned, so the loop is exercised deterministically; real models usually answer with JSON first time.

## How This Demo Was Recorded

The GIF at the top was rendered from a **real** terminal transcript, committed as
[`assets/demo/structured-output.txt`](../../assets/demo/structured-output.txt). It was recorded on 2026-11-27 on
macOS with Python 3.12, from the repository root, with no `MULTIBOT_*` variables set and the `demo-output/` files
deleted first. Each command ran for real, and its stdout and stderr were appended verbatim after a `$ <command>` line:

```bash
jq -c "{required, risk: .properties.risk, steps: (.properties.steps | {minItems, uniqueItems})}" examples/structured-output/launch-plan.schema.json
multi-bot-agentic run --goal "Plan the agent launch" --provider fake --event-log demo-output/output.sqlite --run-id demo --output-schema examples/structured-output/launch-plan.schema.json --output-file demo-output/plan.json | jq -c "{state, steps, output_attempts, output_file}"; echo "exit code: ${PIPESTATUS[0]}"
multi-bot-agentic replay --event-log demo-output/output.sqlite --run-id demo --format text | grep -E "validating|correction"
jq -c . demo-output/plan.json
multi-bot-agentic report --event-log demo-output/output.sqlite --run-id demo | jq -c ".runs[0].output | {valid, attempts, retries, schema_sha256: .schema_sha256[0:12]}"
multi-bot-agentic run --goal "Plan the agent launch" --provider fake --event-log demo-output/output.sqlite --run-id strict --output-schema examples/structured-output/launch-plan.schema.json --output-retries 0 | jq -c "{state, steps, output_errors}"; echo "exit code: ${PIPESTATUS[0]}"
multi-bot-agentic fork --event-log demo-output/output.sqlite --run-id strict --at-step 3 --new-run-id rescue --output-retries 1 --provider fake --output-file demo-output/rescued.json | jq -c "{run_id, state, steps, output_attempts}"
multi-bot-agentic trace --event-log demo-output/output.sqlite --run-id demo --format mermaid | grep -E "Note over O: (finish|output)|correction"
multi-bot-agentic eval --event-log-dir demo-output/eval-output | jq -c "{pass_rate, mean_output_score, structured: [.scenarios[] | select(.actual_output) | {scenario_id, output_score}]}"
```

The transcript was rendered with [`scripts/render_terminal_gif.py`](../../scripts/render_terminal_gif.py) (stdlib
pixel frames stitched by `ffmpeg`, the repository palette, and the public-domain X11 8x13 font). Lines starting with
`$ ` are typed; all other lines are printed as captured:

```bash
python scripts/render_terminal_gif.py assets/demo/structured-output.txt assets/demo/structured-output.gif \
  --rows 32 --title "multi-bot-agentic: structured output with a correction round"
```

## Related

- [Run Fork Guide](RUN_FORK_GUIDE.md): forks and lineage.
- [Checkpoint Resume Guide](CHECKPOINT_RESUME_GUIDE.md): what `resume` restores.
- [Human-in-the-Loop Interrupts Guide](HITL_INTERRUPTS_GUIDE.md): the other run state that waits for someone.
- [Eval Harness Guide](EVAL_HARNESS_GUIDE.md): fixtures and scores.
- [OpenTelemetry Trace Export Guide](OTEL_TRACE_EXPORT_GUIDE.md): span events and attributes.
- [Architecture](../ARCHITECTURE.md#structured-output) and [Safety](../SAFETY.md#structured-output-schemas).
