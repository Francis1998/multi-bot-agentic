# YAML Format Tool User Guide

![YAML format flow](../../assets/demo/yaml-format.gif)

## Why

Agents often exchange configuration, checklist state, or structured notes as
YAML. Full YAML includes anchors, tags, merge keys, and other features that are
unnecessary for model handoffs and easy to interpret inconsistently.
**multi-bot-agentic** includes `yaml_format` as a deterministic, allowlisted
formatter that is safe for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2
workers.

## Usage

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.yaml_format import YamlFormatTool

result = YamlFormatTool().execute(
    ToolInvocation(
        tool_name="yaml_format",
        arguments={
            "text": """
models:
  - GPT-5.5
  - Claude Sonnet 4.6
enabled: true
retries: 2
"""
        },
    )
)
print(result.content)
```

Via the decision-engine directive:

```text
TOOL:yaml_format:models:
  - Gemini 3.x
  - Kimi K2
enabled: true
```

## Supported safe subset

The tool is stdlib-only and intentionally implements a constrained YAML subset:

- block mappings (`key: value`) with deterministic sorted keys;
- block sequences (`- value`);
- nested mappings/sequences via indentation;
- JSON-style flow collections such as `{"b": 1, "a": 2}`;
- scalar strings, finite integers/floats, booleans, and nulls.

Unsupported full-YAML features such as anchors, aliases, tags, document markers,
literal/folded blocks, merge keys, and custom constructors return `ok=False`
structured failures instead of being evaluated.

## Bounds

| Limit | Value |
|---|---|
| Max document chars | 20_000 |
| Output indentation | 2 spaces |
| Mapping key order | Sorted |
| Runtime dependencies | None (stdlib only) |

Empty input, oversized documents, malformed indentation, unsupported syntax, and
non-finite numbers return structured failures.

## Safety

Listed in `SafetyPolicy.allowed_tools` as `yaml_format`. No network, no code
execution, no YAML constructors, no aliases, and no third-party runtime. See
`docs/SAFETY.md`.
