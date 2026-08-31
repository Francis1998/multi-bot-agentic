# base58 Tool Guide

![base58 demo](../../assets/demo/base58.gif)

Encode or decode UTF-8 text with Bitcoin-alphabet Base58 before the next
GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 turn.

## Why

Agent pipelines often need an opaque encoding that avoids lookalike characters
(`0`/`O`/`I`/`l`). Models invent alphabet mistakes. `base58` uses the Bitcoin
Base58 alphabet only, with no network access.

## Usage

```python
tool.execute(
    ToolInvocation(
        tool_name="base58",
        arguments={"text": "hello", "mode": "encode"},
    )
)
```

Decode with `mode=decode`. The `data` argument is accepted as an alias for
`text`. Whitespace in Base58 input is ignored.

## Bounds & Safety

- Max text 20_000 chars
- Modes: `encode` (default) or `decode`
- Alphabet: Bitcoin Base58
- Never executes code or makes network requests
