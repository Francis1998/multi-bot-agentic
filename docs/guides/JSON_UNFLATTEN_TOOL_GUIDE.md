# JSON Unflatten Tool User Guide

![JSON unflatten flow](../../assets/demo/json-unflatten.gif)

## Why

Agents often need flat JSON observations rebuilt into nested objects and arrays
before the next model turn. **multi-bot-agentic** includes `json_unflatten` as a
deterministic, allowlisted stdlib `json` helper that is safe for GPT-5.5 /
Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.

It is the inverse of `json_flatten` for its dotted object paths and bracketed
array indexes, such as `items[0].name`.

## Usage

Programmatic arguments:

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.json_unflatten import JsonUnflattenTool

result = JsonUnflattenTool().execute(
    ToolInvocation(
        tool_name="json_unflatten",
        arguments={
            "text": '{"model":"GPT-5.5","items[0].name":"Claude Sonnet 4.6"}',
            "separator": ".",
        },
    )
)
print(result.content)
```

Via the decision-engine directive:

```text
TOOL:json_unflatten:{"model":"GPT-5.5","items[0].name":"Claude Sonnet 4.6"}
```

## Behavior

Object paths use the requested separator (default `.`), while array indexes use
brackets. Sparse array indexes are filled with JSON `null`. Empty containers
previously emitted by `json_flatten` remain empty containers. Empty, oversized,
malformed, non-object, over-deep, or over-expanded input returns `ok=False`.
Paths that require the same value to be both a leaf and a parent, or both an
object and an array, are rejected as conflicts.

Metadata includes `keys`, `separator`, output `chars`, and input `input_chars`.

## Bounds

| Limit | Value |
|---|---|
| Max input/output chars | 20_000 |
| Max flat keys | 2000 |
| Max array index | 1999 |
| Max path depth | 100 |
| Default separator | `.` |
| Parser | Python stdlib `json` only |
| Network access | none |

## Safety

Listed in `SafetyPolicy.allowed_tools` as `json_unflatten`. It uses only stdlib
`json`, with no network or code execution. See `docs/SAFETY.md`.
