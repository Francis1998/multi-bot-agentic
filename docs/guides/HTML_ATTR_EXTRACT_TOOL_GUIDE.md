# HTML Attribute Extract Tool User Guide

![HTML attribute extract flow](../../assets/demo/html-attr-extract.gif)

## Why

Agents routinely need attribute values (`href`, `src`, `id`, `class`) from an
HTML snippet before the next LLM turn. Inventing attributes in-model
hallucinates URLs and drifts across turns. **multi-bot-agentic** includes
`html_attr_extract` as a deterministic, allowlisted extractor via stdlib
`html.parser` that is safe for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x /
Kimi K2 workers.

## Usage

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.html_attr_extract import HtmlAttrExtractTool

result = HtmlAttrExtractTool().execute(
    ToolInvocation(
        tool_name="html_attr_extract",
        arguments={
            "text": '<a href="/a">A</a><img src="/i.png"/><a href="/b">B</a>',
            "attr": "href",
            "tag": "a",
            "max_results": 10,
        },
    )
)
print(result.content)
```

A model requests it with `TOOL:html_attr_extract:<html>` plus `attr` (required)
and optional `tag` / `max_results` arguments.

## Bounds

- Max document size: 20_000 characters
- `attr` is required (case-insensitive match)
- Optional `tag` filters by element name (case-insensitive)
- `max_results` default 100, max 500; truncated results set metadata `truncated`

## Safety

- Stdlib `html.parser` only — no code execution, no network
- Allowlisted in `SafetyPolicy.allowed_tools`
- Registered in `build_default_tools`

## Suggested repo metadata

- **Description:** Multi-bot agentic runtime with allowlisted tools, safety
  policy, and GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.
- **Topics:** `agentic-ai`, `multi-agent`, `llm-tools`, `python`, `safety`
