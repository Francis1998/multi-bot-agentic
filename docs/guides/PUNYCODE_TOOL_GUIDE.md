# punycode Tool Guide

![punycode demo](../../assets/demo/punycode.gif)

Internationalized domain names need xn-- Punycode before the next GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 turn.

## Why

Internationalized domain names need xn-- Punycode. Models invent encodings. Gap fill vs agent toolkits that ship URL parsers but skip IDNA. Uses stdlib encodings.idna only.

## Usage

```python
tool.execute(ToolInvocation(tool_name="punycode", arguments={"text": "münchen.de", "mode": "encode"}))
```

## Bounds & Safety

- Max text 2000 chars
- Modes: `encode` (default) or `decode`
- Stdlib IDNA codec only
- Never executes code or makes network requests
