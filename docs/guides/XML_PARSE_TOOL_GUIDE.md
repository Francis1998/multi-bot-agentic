# XML Parse Tool User Guide

![XML parse flow](../../assets/demo/xml-parse.gif)

## Why

Agent toolkits (LangChain tools, CrewAI helpers, OpenAI/Anthropic agent demos)
often ship XML helpers so models can exchange structured snippets without
inventing element trees. Pasting raw XML into prompts is error-prone (lost
attributes, flattened nesting, unsafe declarations). **multi-bot-agentic**
includes `xml_parse` as a deterministic, allowlisted parser that is safe for
GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.

## Usage

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.xml_parse import XmlParseTool

result = XmlParseTool().execute(
    ToolInvocation(
        tool_name="xml_parse",
        arguments={
            "text": """<models>
  <model vendor="OpenAI">GPT-5.5</model>
  <model vendor="Anthropic">Claude Sonnet 4.6</model>
</models>"""
        },
    )
)
print(result.content)
```

Via the decision-engine directive:

```text
TOOL:xml_parse:<models><model vendor="Google">Gemini 3.x</model></models>
```

## Behavior

Parsing uses the stdlib `xml.etree.ElementTree` module only. Before parse, the
tool scans for `<!DOCTYPE` and `<!ENTITY` (case-insensitive) and rejects those
documents to block XXE-style entity expansion. On success it returns a compact
indented text tree:

- element tag names (namespace URIs stripped);
- attributes as `@key=value` pairs;
- direct text children quoted when needed;
- depth capped at 12 levels;
- at most 500 elements rendered (with `... [element limit]` / `... [depth limit]`
  markers when truncated).

Empty documents, oversized input, disallowed declarations, and malformed XML
return `ok=False` structured failures instead of being evaluated.

## Bounds

| Limit | Value |
|---|---|
| Max document chars | 20_000 |
| Max render depth | 12 |
| Max rendered elements | 500 |
| Parse runtime | stdlib `xml.etree.ElementTree` only |

## Safety

Listed in `SafetyPolicy.allowed_tools` as `xml_parse`. No network, no code
execution, and no constructor hooks. DOCTYPE/ENTITY declarations are rejected
before parse. See `docs/SAFETY.md`.
