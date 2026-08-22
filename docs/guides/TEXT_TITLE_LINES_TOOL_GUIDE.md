# Text Title Lines Tool User Guide

![Text title lines flow](../../assets/demo/text-title-lines.gif)

## Why

Agents sometimes need display titles for every heading or record without losing
a document's line structure. **multi-bot-agentic** includes `text_title_lines`
as a deterministic, allowlisted per-line formatter that is distinct from the
whole-document `text_case` tool and safe for GPT-5.5 / Claude Sonnet 4.6 /
Gemini 3.x / Kimi K2 workers.

## Usage

Programmatic arguments:

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.text_title_lines import TextTitleLinesTool

result = TextTitleLinesTool().execute(
    ToolInvocation(
        tool_name="text_title_lines",
        arguments={
            "text": "gpt-5.5 models\nclaude sonnet 4.6",
            "skip_empty": True,
            "lowercase_first": True,
        },
    )
)
print(result.content)
```

Via the decision-engine directive:

```text
TOOL:text_title_lines:GPT-5.5 models
Gemini 3.x models<<<TEXT_TITLE_LINES>>>true:true
```

The sentinel suffix is `skip_empty[:lowercase_first]`. An empty suffix uses
`skip_empty=true` and `lowercase_first=false`.

## Behavior

Each line is independently passed through `str.title()`. With
`lowercase_first=true`, the line body is lowercased first so mixed-case input
title-cases consistently. Original `\n`, `\r\n`, and `\r` endings are retained.
With `skip_empty=true`, whitespace-only line bodies are preserved unchanged;
with `false`, those bodies are also title-cased.

Empty, oversized, invalid-option, duplicate-sentinel, and oversized-output
requests return `ok=False`.

## Bounds

| Limit | Value |
|---|---|
| Max input/output chars | 20,000 |
| Default skip empty | `true` |
| Default lowercase first | `false` |
| Network access | none |

## Safety

Listed in `SafetyPolicy.allowed_tools` as `text_title_lines`. It uses bounded
stdlib string operations only, with no network, file access, or code execution.
See `docs/SAFETY.md`.
