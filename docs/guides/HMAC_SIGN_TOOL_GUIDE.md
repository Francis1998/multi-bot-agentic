# hmac_sign Tool Guide

![hmac_sign demo](../../assets/demo/hmac-sign.gif)

Sign a UTF-8 payload with HMAC before the next GPT-5.5 / Claude Sonnet 4.6 /
Gemini 3.x / Kimi K2 turn.

## Why

Webhook signing utilities in LangChain / n8n agent stacks need a deterministic
HMAC digest. Models cannot reliably compute keyed digests. `hmac_sign` uses
stdlib `hmac` + `hashlib` only and never logs the secret key.

## Usage

```python
tool.execute(
    ToolInvocation(
        tool_name="hmac_sign",
        arguments={
            "text": "payload",
            "key": "webhook-secret",
            "algorithm": "sha256",
            "output": "hex",
        },
    )
)
```

## Bounds & Safety

- Max text 20_000 chars; max key 1_024 chars
- Algorithms: `sha256` (default), `sha1`, `sha512`
- Output: `hex` (default) or `base64`
- Secret never appears in result content or metadata
- Never executes code or makes network requests
