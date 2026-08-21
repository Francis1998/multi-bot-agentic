# Text Slug Lines Tool User Guide

![Text slug lines flow](../../assets/demo/text-slug-lines.gif)

## Why

Agents sometimes need one stable slug per heading or record without losing a
document's line structure. **multi-bot-agentic** includes `text_slug_lines` as
a deterministic, allowlisted per-line formatter that is distinct from the
single-string `slugify` tool and safe for GPT-5.5 / Claude Sonnet 4.6 /
Gemini 3.x / Kimi K2 workers.

## Usage

Programmatic arguments:

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.text_slug_lines import TextSlugLinesTool

result = TextSlugLinesTool().execute(
    ToolInvocation(
        tool_name="text_slug_lines",
        arguments={
            "text": "Café Models\nClaude Sonnet 4.6",
            "separator": "-",
            "lowercase": True,
            "skip_empty": True,
        },
    )
)
print(result.content)
```

Via the decision-engine directive:

```text
TOOL:text_slug_lines:GPT-5.5 Models
Gemini 3.x Models<<<TEXT_SLUG_LINES>>>_:false:true
```

The sentinel suffix is `separator[:lowercase[:skip_empty]]`. An empty suffix
uses separator `-`, `lowercase=true`, and `skip_empty=true`.

## Behavior

Each line is Unicode-normalized, converted to ASCII, optionally lowercased, and
split into alphanumeric runs joined by `separator`. Original `\n`, `\r\n`, and
`\r` endings are retained. With `skip_empty=true`, whitespace-only line bodies
are preserved; with `false`, those bodies are normalized to empty strings.
Lines containing only punctuation may also produce an empty slug.

Empty, oversized, invalid-option, duplicate-sentinel, and oversized-output
requests return `ok=False`.

## Bounds

| Limit | Value |
|---|---|
| Max input/output chars | 20,000 |
| Separator | 1..8 ASCII letters, digits, `_`, or `-` |
| Default separator | `-` |
| Default lowercase / skip empty | `true` / `true` |
| Network access | none |

## Safety

Listed in `SafetyPolicy.allowed_tools` as `text_slug_lines`. It uses bounded
stdlib string operations only, with no network, file access, or code execution.
See `docs/SAFETY.md`.
