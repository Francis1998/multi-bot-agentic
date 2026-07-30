# HTML Markdown Tool User Guide

![HTML markdown flow](../../assets/demo/html-markdown.gif)

## Why

Popular agent frameworks (LangChain document loaders, CrewAI helpers, OpenAI
Agents SDK examples) ship a dedicated **HTML → Markdown** helper so the model
does not invent structure, drop links, or leak `<script>` bodies. **multi-bot-agentic**
now includes the same capability as a deterministic, allowlisted tool — safe for
GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.

## Usage

Programmatic:

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.html_markdown import HtmlMarkdownTool

result = HtmlMarkdownTool().execute(
    ToolInvocation(
        tool_name="html_markdown",
        arguments={
            "text": (
                "<h1>Hello</h1>"
                '<p>See <a href="https://example.com">docs</a> '
                "and <strong>bold</strong>.</p>"
                "<ul><li>one</li><li>two</li></ul>"
            ),
        },
    )
)
print(result.content)
```

Via the decision-engine directive:

```text
TOOL:html_markdown:<h2>Notes</h2><p><em>Italic</em> and <code>x</code></p>
```

## Converted elements

| HTML | Markdown |
|---|---|
| `h1`–`h6` | `#` … `######` headings |
| `a href` | `[text](url)` links |
| `ul` / `ol` / `li` | `-` / numbered lists |
| `strong` / `b` | `**bold**` |
| `em` / `i` | `*italic*` |
| `code` / `pre` | `` `inline` `` / fenced blocks |
| `p` / `br` | paragraphs / line breaks |

## Bounds

| Limit | Value |
|---|---|
| Max document chars | 20_000 |
| Rejected tags | `script`, `style` |

Empty input, oversized documents, markup-only documents, and any document that
contains `<script>` or `<style>` return `ok=False` structured failures — never
exceptions into the run loop. Named/numeric HTML entities are unescaped. The
tool never fetches URLs from `href` attributes.

## Safety

Listed in `SafetyPolicy.allowed_tools` as `html_markdown`. No network, no code
execution — stdlib `html.parser` only. See `docs/SAFETY.md`.
