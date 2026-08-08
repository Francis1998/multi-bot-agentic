# YAML to JSON Tool User Guide

![YAML to JSON flow](../../assets/demo/yaml-to-json.gif)

## Why

Agents often exchange configuration as YAML and need a portable JSON payload
for the next API or tool step. Full YAML includes anchors, tags, and
constructors that are unsafe for model handoffs. **multi-bot-agentic** includes
`yaml_to_json` as a deterministic, allowlisted converter that reuses the same
stdlib-only safe YAML subset as `yaml_format` — no PyYAML dependency — and is
safe for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.

## Usage

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.yaml_to_json import YamlToJsonTool

result = YamlToJsonTool().execute(
    ToolInvocation(
        tool_name="yaml_to_json",
        arguments={
            "text": """
models:
  - GPT-5.5
  - Claude Sonnet 4.6
enabled: true
"""
        },
    )
)
print(result.content)
```

Via the decision-engine directive:

```text
TOOL:yaml_to_json:models:
  - Gemini 3.x
  - Kimi K2
enabled: true
```

## Supported safe subset

Same constrained YAML subset as `yaml_format`:

- block mappings / sequences
- JSON-style flow collections
- scalar strings, finite numbers, booleans, null

Unsupported features (anchors, aliases, tags, document markers, constructors,
literal/folded blocks) return `ok=False` structured failures instead of being
evaluated. There is no `yaml.load` path — only the safe subset parser.

## Bounds

| Limit | Value |
|---|---|
| Max document chars | 20_000 |
| Max serialized JSON chars | 20_000 |
| Output | sorted keys, 2-space indent |
| Runtime dependencies | None (stdlib + shared yaml_format subset) |

## Safety

Listed in `SafetyPolicy.allowed_tools` as `yaml_to_json`. No network, no code
execution, no YAML constructors, no third-party YAML runtime. See
`docs/SAFETY.md`.
