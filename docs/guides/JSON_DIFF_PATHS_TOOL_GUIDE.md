# JSON Diff Paths Tool User Guide

![JSON diff paths flow](../../assets/demo/json-diff-paths.gif)

## Why

Agents sometimes need a compact account of where two JSON observations differ
without carrying both documents into the next model turn. **multi-bot-agentic**
includes `json_diff_paths` as a deterministic, allowlisted stdlib `json` helper
that is safe for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.

Unlike a text diff, the result identifies JSON structure with the same dotted
object keys and bracketed array indexes used by `json_flatten`.

## Usage

Programmatic arguments:

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.json_diff_paths import JsonDiffPathsTool

result = JsonDiffPathsTool().execute(
    ToolInvocation(
        tool_name="json_diff_paths",
        arguments={
            "text": '{"model":"GPT-5.5","active":true}',
            "other": '{"model":"Claude Sonnet 4.6","active":false}',
        },
    )
)
print(result.content)
```

Via the decision-engine directive:

```text
TOOL:json_diff_paths:{"model":"Gemini 3.x"}<<<JSON_DIFF_PATHS>>>{"model":"Kimi K2"}
```

## Behavior

The result is a sorted JSON list such as `["agents[0].active", "model"]`.
Changed scalar values, missing object keys, and missing array indexes report
their exact path. A root scalar or root type change reports `$`. Equal documents
return `[]`. JSON value types are compared strictly, so booleans do not compare
equal to numbers. Empty, oversized, malformed, non-finite, duplicate-sentinel,
over-expanded, or oversized-output requests return `ok=False`.

Metadata includes the number of `paths` and each document's character count.

## Bounds

| Limit | Value |
|---|---|
| Max chars per input document | 20_000 |
| Max differing paths | 2000 |
| Max output chars | 20_000 |
| Parser | Python stdlib `json` only |
| Network access | none |

## Safety

Listed in `SafetyPolicy.allowed_tools` as `json_diff_paths`. It uses bounded
stdlib parsing and comparison only, with no network or code execution. See
`docs/SAFETY.md`.
