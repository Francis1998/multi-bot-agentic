# TOML Format Tool User Guide

![TOML format flow](../../assets/demo/toml-format.gif)

## Why

Agents often exchange configuration snippets as TOML (`pyproject.toml` fragments,
runtime flags, or structured handoffs). Full TOML includes dates, times, and
parser-specific edge cases that are easy to mishandle across providers.
**multi-bot-agentic** includes `toml_format` as a deterministic, allowlisted
formatter that is safe for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2
workers.

## Usage

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.toml_format import TomlFormatTool

result = TomlFormatTool().execute(
    ToolInvocation(
        tool_name="toml_format",
        arguments={
            "text": """
models = ["GPT-5.5", "Claude Sonnet 4.6"]
enabled = true
retries = 2
"""
        },
    )
)
print(result.content)
```

Via the decision-engine directive:

```text
TOOL:toml_format:models = ["Gemini 3.x", "Kimi K2"]
enabled = true
```

## Supported subset

Parsing uses stdlib `tomllib` on Python 3.11+, with an optional `tomli` fallback
on older interpreters. Serialization prefers `tomli-w` when installed; otherwise
a small recursive dumper emits:

- tables with sorted keys;
- nested tables as dotted `[section]` headers;
- arrays of tables as `[[section]]`;
- scalar strings, finite integers/floats, and booleans;
- inline arrays and empty inline tables (`{}`).

Dates/times, non-finite floats, empty/oversized documents, and missing parsers
return `ok=False` structured failures instead of being evaluated.

## Bounds

| Limit | Value |
|---|---|
| Max document chars | 20_000 |
| Mapping key order | Sorted |
| Value types | dict / list / str / int / float / bool |
| Parse runtime | `tomllib` or `tomli` |
| Dump runtime | `tomli-w` or built-in serializer |

## Safety

Listed in `SafetyPolicy.allowed_tools` as `toml_format`. No network, no code
execution, and no constructor hooks. See `docs/SAFETY.md`.
