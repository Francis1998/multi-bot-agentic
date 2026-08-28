# base32_encode Tool Guide

![base32_encode demo](../../assets/demo/base32-encode.gif)

Encode or decode UTF-8 text with stdlib Base32 before the next GPT-5.5 /
Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 turn.

## Why

Agent pipelines often need a case-insensitive opaque encoding for secrets or
handoff tokens. Models invent padding and alphabet mistakes. `base32_encode`
uses stdlib `base64.b32encode` / `b32decode` with the standard RFC 4648
alphabet only.

## Usage

```python
tool.execute(
    ToolInvocation(
        tool_name="base32_encode",
        arguments={"text": "hello", "mode": "encode"},
    )
)
```

Decode with `mode=decode`. Whitespace in Base32 input is ignored.

## Bounds & Safety

- Max text 20_000 chars
- Modes: `encode` (default) or `decode`
- Alphabet: standard RFC 4648 Base32
- Never executes code or makes network requests
