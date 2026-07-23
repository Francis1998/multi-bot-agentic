# JSON Path Tool User Guide

![JSON path flow](../../assets/demo/json-path.gif)

## Why

Popular agent frameworks (LangGraph toolkits, OpenAI Agents SDK examples, Claude
tool-use demos) ship dedicated **JSON/path extraction** helpers so the model does
not hallucinate nested values or array bounds. **multi-bot-agentic** now includes
the same capability as a deterministic, allowlisted tool — safe for GPT-5.5 /
Claude Sonnet 4.6 / Gemini 2.5 / Kimi K2 workers.

## Usage

Programmatic (two arguments):

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.json_path import JsonPathTool

result = JsonPathTool().execute(
    ToolInvocation(
        tool_name="json_path",
        arguments={
            "text": '{"items":[{"name":"Ada"},{"name":"Grace"}]}',
            "path": ".items[0].name",
        },
    )
)
print(result.content)  # "Ada"
```

Via the decision-engine directive (single payload + sentinel):

```text
TOOL:json_path:{"items":[{"name":"Ada"}]}<<<JSON_PATH>>>items[0].name
```

Use `path=""` or `path="$"` to return the whole document as pretty JSON.

## Path dialect

This is intentionally small and deterministic, not full jq/JSONPath:

- Object keys: `.foo.bar` or `foo.bar`
- Array indexes: `.items[0].name`
- Whole document: `$` or empty path
- Unsupported: recursive descent (`..`), filters, scripts, pipes, wildcards

## Bounds

| Limit | Value |
|---|---|
| Max document chars | 20_000 |
| Max path chars | 256 |
| Max serialized result chars | 20_000 |

Empty documents, invalid JSON, unsupported path syntax, missing keys, out-of-bounds
indexes, oversized input, and oversized results return `ok=False` structured
failures — never exceptions into the run loop.

## CSV blank-header note

The companion `csv` tool now rejects blank header cells such as `name,` rather
than returning an ambiguous empty column name.

## Safety

Listed in `SafetyPolicy.allowed_tools` as `json_path`. No network, no code
execution — stdlib `json.loads` plus deterministic traversal only. See
`docs/SAFETY.md`.
