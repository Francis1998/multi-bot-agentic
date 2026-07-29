# TOML JSON Bridge Tool User Guide

![TOML JSON bridge flow](../../assets/demo/toml-json.gif)

## Why

Agents often need to move configuration between TOML (`pyproject.toml` fragments,
runtime flags) and JSON (API payloads, prior tool output). Converting by hand is
error-prone across providers. **multi-bot-agentic** includes `toml_json` as a
deterministic, allowlisted bridge that is safe for GPT-5.5 / Claude Sonnet 4.6 /
Gemini 3.x / Kimi K2 workers.

## Usage

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.toml_json import TomlJsonTool

result = TomlJsonTool().execute(
    ToolInvocation(
        tool_name="toml_json",
        arguments={
            "text": """
models = ["GPT-5.5", "Claude Sonnet 4.6"]
enabled = true
""",
            "direction": "to_json",
        },
    )
)
print(result.content)
```

Convert JSON back to TOML:

```python
result = TomlJsonTool().execute(
    ToolInvocation(
        tool_name="toml_json",
        arguments={
            "text": '{"enabled": true, "models": ["Gemini 3.x", "Kimi K2"]}',
            "direction": "to_toml",
        },
    )
)
```

Via the decision-engine directive:

```text
TOOL:toml_json:models = ["Gemini 3.x", "Kimi K2"]
enabled = true
```

Use `direction` in structured invocations when converting JSON to TOML.

## Supported subset

| Direction | Parse | Emit |
|---|---|---|
| `to_json` (default) | `tomllib` / `tomli` | `json.dumps` (sorted keys, 2-space indent) |
| `to_toml` | strict `json.loads` | `tomli-w` or built-in TOML dumper from `toml_format` |

Portable value types only: dict / list / str / int / float / bool. Dates/times,
JSON `null`, non-finite numbers, empty/oversized documents, and missing parsers
return `ok=False` structured failures instead of being evaluated.

## Bounds

| Limit | Value |
|---|---|
| Max document chars | 20_000 |
| Mapping key order | Sorted in output |
| Value types | dict / list / str / int / float / bool |
| Directions | `to_json`, `to_toml` |

## Safety

Listed in `SafetyPolicy.allowed_tools` as `toml_json`. No network, no code
execution, and no constructor hooks. See `docs/SAFETY.md`.
