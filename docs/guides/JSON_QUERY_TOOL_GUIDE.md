# JSON Query Tool User Guide

![JSON query flow](../../assets/demo/json-query.gif)

## Why

`json_path` extracts one nested value. Agents also need to filter JSON arrays or
pluck a field across objects — the gap popular agent runtimes fill with a small
`jq`-style select. Filtering in-model invents keys and drops matches.
**multi-bot-agentic** includes `json_query` as a deterministic, allowlisted
select/pluck helper that is safe for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x /
Kimi K2 workers.

## Usage

Programmatic where-filter:

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.json_query import JsonQueryTool

result = JsonQueryTool().execute(
    ToolInvocation(
        tool_name="json_query",
        arguments={
            "text": '[{"name":"Ada","active":true},{"name":"Bob","active":false}]',
            "mode": "where",
            "field": "active",
            "equals": True,
        },
    )
)
print(result.content)
```

Pluck a field:

```python
result = JsonQueryTool().execute(
    ToolInvocation(
        tool_name="json_query",
        arguments={
            "text": '[{"name":"Ada"},{"name":"Bob"}]',
            "mode": "pluck",
            "field": "name",
        },
    )
)
```

Via the decision-engine directive with sentinel args:

```text
TOOL:json_query:[{"name":"Ada","active":true}]<<<JSON_QUERY>>>{"mode":"where","field":"active","equals":true}
```

## Behavior

Modes:

- `where` (default): keep objects whose `field` equals `equals` (required);
- `pluck`: collect `field` from each object (missing keys yield `null`).

Root JSON must be an array of objects. Empty, oversized, malformed, unsupported
mode, or missing-field/equals input returns `ok=False` structured failures.

## Bounds

| Limit | Value |
|---|---|
| Max text chars | 20_000 |
| Max result chars | 20_000 |
| Max array items | 500 |
| Network access | none |

## Safety

Listed in `SafetyPolicy.allowed_tools` as `json_query`. No network, no code
execution, no script evaluation. See `docs/SAFETY.md`.
