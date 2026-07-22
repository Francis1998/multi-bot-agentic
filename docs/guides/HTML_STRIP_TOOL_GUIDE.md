# HTML Strip Tool User Guide

![HTML strip flow](../../assets/demo/html-strip.gif)

## Why

Popular agent frameworks (LangChain text utilities, CrewAI helpers, OpenAI
Agents SDK examples) ship a dedicated **HTML → plain text** helper so the model
does not invent stripped output or leak `<script>` bodies. **multi-bot-agentic**
now includes the same capability as a deterministic, allowlisted tool — safe for
GPT-5.5 / Claude Sonnet 4.6 / Gemini 2.5 / Kimi K2 workers.

## Usage

Programmatic:

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.html_strip import HtmlStripTool

result = HtmlStripTool().execute(
    ToolInvocation(
        tool_name="html_strip",
        arguments={"text": "<p>Hello <b>world</b></p>"},
    )
)
print(result.content)  # Hello world
```

Via the decision-engine directive:

```text
TOOL:html_strip:<p>Hello <b>world</b></p>
```

## Bounds

| Limit | Value |
|---|---|
| Max document chars | 20_000 |
| Rejected tags | `script`, `style` |

Empty input, oversized documents, markup-only documents, and any document that
contains `<script>` or `<style>` return `ok=False` structured failures — never
exceptions into the run loop. Named/numeric HTML entities are unescaped.

## Calculator finite-literal note

The companion `calculator` tool now rejects bare overflow float literals such as
`1e400` (previously returned as `inf`) so finite-result guarantees hold for both
operations and literals.

## Safety

Listed in `SafetyPolicy.allowed_tools` as `html_strip`. No network, no code
execution — stdlib `html.parser` only. See `docs/SAFETY.md`.
