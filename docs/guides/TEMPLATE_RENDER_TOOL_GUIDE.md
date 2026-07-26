# Template Render Tool User Guide

![Template render flow](../../assets/demo/template-render.gif)

## Why

Popular agent frameworks (LangGraph toolkits, OpenAI Agents SDK examples,
Claude tool-use demos) ship dedicated **template/render** helpers so the model
does not hand-edit final artifacts inconsistently. **multi-bot-agentic** now
includes the same capability as a deterministic, allowlisted tool - safe for
GPT-5.5 / Claude Sonnet 4.6 / Gemini 2.5 / Kimi K2 workers.

## Usage

Programmatic:

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.template_render import TemplateRenderTool

result = TemplateRenderTool().execute(
    ToolInvocation(
        tool_name="template_render",
        arguments={
            "template": "<p>Hello {name}</p>",
            "variables": {"name": "Ada <admin>"},
        },
    )
)
print(result.content)  # <p>Hello Ada &lt;admin&gt;</p>
```

Via the decision-engine directive (sentinel embeds JSON variables):

```text
TOOL:template_render:Hello {{ name }}!<<<TEMPLATE_VARS>>>{"name":"Grace & Hopper"}
```

The tool accepts `{name}` and Jinja-like `{{ name }}` placeholders. Placeholder
names must be simple identifiers (`A-Za-z_` followed by letters, digits, or
underscores). Expressions, filters, attribute access, and literal brace syntax
are rejected instead of evaluated.

## Bounds

| Limit | Value |
|---|---|
| Max template chars | 20_000 |
| Max variables | 100 |
| Max variable name chars | 64 |
| Max variable value chars | 4_000 |
| Max rendered output chars | 40_000 |
| Variable escaping | HTML escaping, always on |

Missing variables, invalid JSON, unsupported brace syntax, non-scalar variable
values, oversized inputs, and output overflow return `ok=False` structured
failures - never exceptions into the run loop.

## Directive whitespace note

The decision parser now preserves leading and trailing tool payload whitespace
when it parses `TOOL:name:<payload>`. This matters for templates because spaces,
newlines, and indentation are part of the artifact being rendered.

## Safety

Listed in `SafetyPolicy.allowed_tools` as `template_render`. No network, no code
execution, no `eval`, no filters, no attribute lookup. See `docs/SAFETY.md`.
