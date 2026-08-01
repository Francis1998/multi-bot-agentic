# Text Wrap Tool User Guide

![Text wrap flow](../../assets/demo/text-wrap.gif)

## Why

Agents routinely need to reflow long lines for logs, rationales, or bounded
previews before the next LLM turn. Wrapping in-model is unreliable. **multi-bot-agentic**
includes `text_wrap` as a deterministic, allowlisted wrapper via stdlib
`textwrap` that is safe for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2
workers.

## Usage

Programmatic:

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.text_wrap import TextWrapTool

result = TextWrapTool().execute(
    ToolInvocation(
        tool_name="text_wrap",
        arguments={"text": "GPT-5.5 Claude Sonnet 4.6", "width": 12, "mode": "wrap"},
    )
)
print(result.content)
```

Fill a paragraph to one reflowed block:

```python
result = TextWrapTool().execute(
    ToolInvocation(
        tool_name="text_wrap",
        arguments={"text": "one two three four five", "width": 20, "mode": "fill"},
    )
)
```

Via the decision-engine directive:

```text
TOOL:text_wrap:long observation text that should be wrapped
```

## Behavior

Modes:

- `wrap` (default): joins `textwrap.wrap` segments with newlines;
- `fill`: returns a single paragraph via `textwrap.fill`.

`width` defaults to 80 and must be between 1 and 500.

Metadata reports `width`, `mode`, `lines`, and output `chars`.

Empty, oversized, invalid-width, or unsupported-mode input returns `ok=False`
structured failures.

## Bounds

| Limit | Value |
|---|---|
| Max text chars | 20_000 |
| Width range | 1..500 |
| Network access | none |

## Safety

Listed in `SafetyPolicy.allowed_tools` as `text_wrap`. No network, no code
execution. See `docs/SAFETY.md`.
