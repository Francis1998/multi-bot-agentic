# Text Sort Lines Tool User Guide

![Text sort lines flow](../../assets/demo/text-sort-lines.gif)

## Why

Popular agent frameworks (LangGraph toolkits, OpenAI Agents SDK examples, Claude
tool-use demos) ship helpers that **normalize multi-line text** so the model does
not invent ordering or drop duplicates inconsistently. **multi-bot-agentic** now
includes the same capability as a deterministic, allowlisted tool — safe for
GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.

## Usage

Programmatic:

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.text_sort_lines import TextSortLinesTool

result = TextSortLinesTool().execute(
    ToolInvocation(
        tool_name="text_sort_lines",
        arguments={
            "text": "Kimi K2\nGPT-5.5\nClaude Sonnet 4.6\nGemini 3.x\nGPT-5.5",
            "order": "asc",
            "unique": True,
        },
    )
)
print(result.content)
# Claude Sonnet 4.6
# GPT-5.5
# Gemini 3.x
# Kimi K2
```

Via the decision-engine directive (defaults: ascending, keep duplicates):

```text
TOOL:text_sort_lines:Gemini 3.x
Claude Sonnet 4.6
GPT-5.5
Kimi K2
```

## Bounds

| Limit | Value |
|---|---|
| Max document chars | 20_000 |
| Default `order` | `asc` |
| Supported `order` | `asc`, `ascending`, `desc`, `descending` |
| Default `unique` | `false` |

Empty text, oversized input, unsupported `order`, and non-boolean `unique`
return `ok=False` structured failures — never exceptions into the run loop.

## Safety

Listed in `SafetyPolicy.allowed_tools` as `text_sort_lines`. No network, no code
execution — stdlib sorting only. See `docs/SAFETY.md`.
