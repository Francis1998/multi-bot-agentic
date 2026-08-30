# JWT Encode Tool User Guide

![JWT encode flow](../../assets/demo/jwt-encode.gif)

## Why

Agents often need to mint HS256 JWTs for webhook handoffs or test fixtures
alongside the existing decode-only `jwt_decode` inspector. Encoding in-model
is error-prone (padding mistakes, wrong HMAC input). **multi-bot-agentic**
includes `jwt_encode` as an allowlisted stdlib encoder (no PyJWT). It is safe
for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers — and it
never makes network requests.

## Usage

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.jwt_encode import JwtEncodeTool

result = JwtEncodeTool().execute(
    ToolInvocation(
        tool_name="jwt_encode",
        arguments={
            "payload": {"sub": "alice"},
            "secret": "test-secret",
            "headers": {"kid": "kid-1"},
        },
    )
)
print(result.content)
```

A model requests it with `TOOL:jwt_encode:<payload-json>` plus secret arguments.

## Behavior

- Builds `header.payload.signature` with HS256 only (`alg` is always forced)
- Accepts `payload` as a JSON object dict or JSON string
- Optional `headers` dict merges into the JWT header
- Returns the compact JWT string; secret is never logged

Malformed payload JSON, non-object payloads, empty secret, and oversized
payload/secret return `ok=False` structured failures — never exceptions into
the run loop.

## Bounds

| Limit | Value |
|---|---|
| Max payload bytes (canonical JSON) | 8_192 |
| Max secret chars | 1_024 |
| Algorithm | HS256 only |
| Network access | none |

## Safety

Listed in `SafetyPolicy.allowed_tools` as `jwt_encode`. No network, no code
execution, stdlib `hmac`/`hashlib`/`base64` only. Pair with `jwt_decode` for
inspection; never trust decoded claims for authorization without proper
verification elsewhere. See `docs/SAFETY.md`.
