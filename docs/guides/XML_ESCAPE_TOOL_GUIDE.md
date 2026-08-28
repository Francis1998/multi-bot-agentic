# xml_escape Tool Guide

![xml_escape demo](../../assets/demo/xml-escape.gif)

Escape or unescape XML special characters before the next GPT-5.5 /
Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 turn.

## Why

Agent pipelines that build or scrape XML handoffs need deterministic escaping
of `&`, `<`, and `>`. Models miss ampersands or double-escape. `xml_escape`
uses stdlib `xml.sax.saxutils.escape` / `unescape`.

## Usage

```python
tool.execute(
    ToolInvocation(
        tool_name="xml_escape",
        arguments={"text": "A <B> & C", "mode": "escape"},
    )
)
```

Unescape with `mode=unescape`.

## Bounds & Safety

- Max text 20_000 chars
- Modes: `escape` (default) or `unescape`
- Never executes code or makes network requests
