# Line Number Tool User Guide

![Line number flow](../../assets/demo/line-number.gif)

## Why

Agents routinely need stable line numbers when quoting logs, diffs, or source
snippets. Inventing numbers in-model drifts across turns. **multi-bot-agentic**
includes `line_number` as a deterministic, allowlisted annotator that is safe
for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.

## Usage

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.line_number import LineNumberTool

result = LineNumberTool().execute(
    ToolInvocation(
        tool_name="line_number",
        arguments={"text": "alpha\nbeta\n", "start": 1, "separator": "| "},
    )
)
print(result.content)
```

A model requests it with `TOOL:line_number:<text>`.

## Bounds

- Max document size: 20_000 characters
- Max lines: 2_000
- `start` must be an integer >= 0 (default 1)
- `separator` must not contain newlines (default `"| "`)

## Safety

- Stdlib string ops only — no code execution, no network
- Allowlisted in `SafetyPolicy.allowed_tools`
- Registered in `build_default_tools`

## Suggested repo metadata

- **Description:** Multi-bot agentic runtime with allowlisted tools, safety
  policy, and GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.
- **Topics:** `agentic-ai`, `multi-agent`, `llm-tools`, `python`, `safety`
