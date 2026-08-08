# JSON Pointer Tool User Guide

![JSON Pointer flow](../../assets/demo/json-pointer.gif)

## Why

Popular agent frameworks ship JSON Pointer helpers so models do not invent
nested paths. **multi-bot-agentic** already has `json_path` (dot/`[index]`
dialect). This tool adds the IETF **RFC 6901** dialect (`/foo/0/bar`) as a
separate allowlisted extractor — safe for GPT-5.5 / Claude Sonnet 4.6 /
Gemini 3.x / Kimi K2 workers.

## Usage

Programmatic (two arguments):

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.json_pointer import JsonPointerTool

result = JsonPointerTool().execute(
    ToolInvocation(
        tool_name="json_pointer",
        arguments={
            "text": '{"foo":[{"bar":"Ada"}]}',
            "pointer": "/foo/0/bar",
        },
    )
)
print(result.content)  # "Ada"
```

Via the decision-engine directive (single payload + sentinel):

```text
TOOL:json_pointer:{"foo":[{"bar":"Ada"}]}<<<JSON_POINTER>>>/foo/0/bar
```

Use `pointer=""` (empty string) to return the whole document as pretty JSON.

## Pointer dialect (RFC 6901)

- Absolute pointers start with `/`
- Empty pointer selects the whole document
- Escapes: `~1` → `/`, `~0` → `~`
- Array indexes are decimal integers without leading zeros (except `0`)
- Unsupported for extraction: array `-` append token, filters, scripts

This is distinct from `json_path` (`.foo[0].bar`).

## Bounds

| Limit | Value |
|---|---|
| Max document chars | 20_000 |
| Max pointer chars | 512 |
| Max serialized result chars | 20_000 |

Empty documents, invalid JSON, bad pointer syntax, missing keys, out-of-bounds
indexes, oversized input, and oversized results return `ok=False` structured
failures — never exceptions into the run loop.

## Safety

Listed in `SafetyPolicy.allowed_tools` as `json_pointer`. No network, no code
execution — stdlib `json.loads` plus deterministic RFC 6901 traversal only. See
`docs/SAFETY.md`.
