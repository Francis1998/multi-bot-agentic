# HTML Entities Tool User Guide

![HTML entities flow](../../assets/demo/html-entities.gif)

## Why

Agents routinely need to escape or unescape HTML entities before rendering
snippets or comparing scraped text. Encoding in-model is unreliable.
**multi-bot-agentic** includes `html_entities` as a deterministic, allowlisted
encoder/decoder via stdlib `html` that is safe for GPT-5.5 / Claude Sonnet 4.6 /
Gemini 3.x / Kimi K2 workers.

## Usage

Programmatic:

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.html_entities import HtmlEntitiesTool

result = HtmlEntitiesTool().execute(
    ToolInvocation(
        tool_name="html_entities",
        arguments={"text": "A <B> & C", "mode": "encode"},
    )
)
print(result.content)
```

Decode named and numeric entities:

```python
result = HtmlEntitiesTool().execute(
    ToolInvocation(
        tool_name="html_entities",
        arguments={"text": "A &lt;B&gt; &#38; C", "mode": "decode"},
    )
)
```

Via the decision-engine directive:

```text
TOOL:html_entities:A <B> & C
```

## Behavior

Modes:

- `encode` (default): `html.escape`; optional `quote` (default true) escapes quotes;
- `decode`: `html.unescape` for named and numeric entities.

Metadata reports `mode`, `quote`, and output `chars`.

Empty, oversized, unsupported-mode, or invalid-quote input returns `ok=False`
structured failures.

## Bounds

| Limit | Value |
|---|---|
| Max text chars | 20_000 |
| Network access | none |

## Safety

Listed in `SafetyPolicy.allowed_tools` as `html_entities`. No network, no code
execution. See `docs/SAFETY.md`.
