# base85 Tool Guide

![base85 demo](../../assets/demo/base85.gif)

Denser-than-Base64 opaque handoffs before the next GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 turn.

## Why

Denser-than-Base64 opaque handoffs. Complements existing base32/base58/base64 tools (parity with encoding suites in popular agent runtimes).

## Usage

```python
tool.execute(ToolInvocation(tool_name="base85", arguments={"text": "hello", "mode": "encode"}))
```

## Bounds & Safety

- Max text 20_000 chars
- Modes: `encode` (default) or `decode`
- Alphabet: Adobe ASCII85 via stdlib base64.a85
- Never executes code or makes network requests
