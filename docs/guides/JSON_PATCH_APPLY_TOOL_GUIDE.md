# JSON Patch Apply Tool User Guide

![JSON Patch apply flow](../../assets/demo/json-patch-apply.gif)

## Why

Agents often need to apply precise JSON updates without regenerating a complete
document. **multi-bot-agentic** includes `json_patch_apply` as a deterministic,
allowlisted RFC 6902 helper that is safe for GPT-5.5 / Claude Sonnet 4.6 /
Gemini 3.x / Kimi K2 workers.

Unlike `json_merge_patch`, JSON Patch addresses exact values with RFC 6901
pointers and supports assertions and array edits.

## Usage

Programmatic arguments:

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.json_patch_apply import JsonPatchApplyTool

result = JsonPatchApplyTool().execute(
    ToolInvocation(
        tool_name="json_patch_apply",
        arguments={
            "text": '{"model":"GPT-5.5","active":false}',
            "patch": [
                {"op": "replace", "path": "/model", "value": "Claude Sonnet 4.6"},
                {"op": "replace", "path": "/active", "value": True},
            ],
        },
    )
)
print(result.content)
```

Via the decision-engine directive:

```text
TOOL:json_patch_apply:{"model":"Gemini 3.x"}<<<JSON_PATCH>>>[{"op":"replace","path":"/model","value":"Kimi K2"}]
```

## Behavior

The tool applies RFC 6902 `add`, `remove`, `replace`, `move`, `copy`, and `test`
operations in array order. Paths use RFC 6901 JSON Pointer syntax, including the
empty root path and `~0`/`~1` escapes. `-` appends to an array for `add`.
`copy` deep-copies values, and a failed `test` returns `ok=False`.

The patch is applied to an internal copy; failures never return a partially
patched document. Empty, malformed, non-finite, invalid-pointer, out-of-bounds,
over-limit, and oversized-output requests return `ok=False`. Metadata includes
operation and input/output character counts.

## Bounds

| Limit | Value |
|---|---|
| Max JSON document chars | 20,000 |
| Max patch chars | 20,000 |
| Max operations | 200 |
| Max output chars | 20,000 |
| Parser/runtime | Python stdlib only |
| Network access | none |

## Safety

Listed in `SafetyPolicy.allowed_tools` as `json_patch_apply`. It uses bounded
stdlib parsing and in-memory data operations only, with no network, file access,
or code execution. See `docs/SAFETY.md`.
