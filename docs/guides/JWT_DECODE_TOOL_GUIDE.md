# JWT Decode Tool User Guide

![JWT decode flow](../../assets/demo/jwt-decode.gif)

## Why

Agents often need to inspect JWT claims (issuer, subject, expiry) relayed by
an upstream step without treating the token as authenticated. Decoding in-model
is error-prone (padding mistakes, truncated payloads). **multi-bot-agentic**
includes `jwt_decode` as an allowlisted base64url decoder for header + payload
only. It is safe for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2
workers — and it **never verifies signatures**.

## Usage

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.jwt_decode import JwtDecodeTool

token = "eyJhbGciOiJub25lIn0.eyJzdWIiOiJhbGljZSJ9.sig"
result = JwtDecodeTool().execute(ToolInvocation(tool_name="jwt_decode", arguments={"text": token}))
print(result.content)
```

A model requests it with `TOOL:jwt_decode:<jwt>`.

## Behavior

- Splits the token on `.` and requires exactly three segments
- Base64url-decodes header and payload into JSON objects
- **Ignores the signature segment; never verifies or trusts claims**
- Returns pretty JSON: `{"header": {...}, "payload": {...}}`
- Metadata always includes `verified: false` and `trusted: false`

Malformed segments, non-object JSON, empty input, and oversized tokens return
`ok=False` structured failures — never exceptions into the run loop.

## Bounds

| Limit | Value |
|---|---|
| Max token chars | 20_000 |
| Max result chars | 20_000 |
| Signature verification | **none** (by design) |
| Network access | none |

## Safety

Listed in `SafetyPolicy.allowed_tools` as `jwt_decode`. No network, no code
execution, **no cryptographic verification**. Decoded claims are opaque
inspection aids only — do not authorize actions from this output. See
`docs/SAFETY.md`.
