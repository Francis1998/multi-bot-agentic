# JSON Merge Patch Tool User Guide

![JSON Merge Patch flow](../../assets/demo/json-merge-patch.gif)

## Why

Agents routinely need to apply partial JSON updates onto a base document without
losing sibling keys. Merging in-model invents fields and drops nested maps.
**multi-bot-agentic** includes `json_merge_patch` as a deterministic RFC 7396
merge via stdlib `json` that is safe for GPT-5.5 / Claude Sonnet 4.6 /
Gemini 3.x / Kimi K2 workers.

## Usage

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.json_merge_patch import JsonMergePatchTool

result = JsonMergePatchTool().execute(
    ToolInvocation(
        tool_name="json_merge_patch",
        arguments={
            "base": '{"a":1,"b":{"c":2}}',
            "patch": '{"b":{"c":9},"d":3}',
        },
    )
)
print(result.content)
```

Combined form: `{"a":1}<<<PATCH>>>{"b":2}`.

## Bounds

- Max base/patch size: 20_000 characters each
- Max merge depth: 32
- `null` patch values delete keys (RFC 7396)
- Non-object patches replace the target value

## Safety

- Stdlib `json` only — no code execution, no network
- Allowlisted in `SafetyPolicy.allowed_tools`
- Registered in `build_default_tools`

## Suggested repo metadata

- **Description:** Multi-bot agentic runtime with allowlisted tools, safety
  policy, and GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.
- **Topics:** `agentic-ai`, `multi-agent`, `llm-tools`, `python`, `safety`
