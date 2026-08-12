# Hex Encode Tool User Guide

![Hex encode flow](../../assets/demo/hex-encode.gif)

## Why

Agents often need a stable hexadecimal representation of a UTF-8 payload before
hashing, embedding, or comparing opaque blobs. **multi-bot-agentic** includes
`hex_encode` as a deterministic, allowlisted transform that is safe for GPT-5.5
/ Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.

## Usage

Programmatic arguments:

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.hex_encode import HexEncodeTool

result = HexEncodeTool().execute(
    ToolInvocation(
        tool_name="hex_encode",
        arguments={"text": "hello", "uppercase": False},
    )
)
print(result.content)
```

Via the decision-engine directive (single payload + sentinel):

```text
TOOL:hex_encode:hello<<<HEX_ENCODE>>>true
```

The sentinel suffix accepts `true`/`false`, `1`/`0`, `yes`/`no`, or
`on`/`off`. An omitted or empty suffix uses the default `uppercase=false`.

## Behavior

The tool encodes the input string as UTF-8 bytes, then emits the hexadecimal
digest. With `uppercase=true`, hex digits `a-f` become `A-F`. Empty, oversized,
duplicate-sentinel, and invalid `uppercase` inputs return `ok=False`.

## Bounds

| Limit | Value |
|---|---|
| Max text chars | 20_000 |
| Default uppercase | false |
| Network access | none |

## Safety

Listed in `SafetyPolicy.allowed_tools` as `hex_encode`. It uses only stdlib
`bytes.hex`, with no network or code execution. See `docs/SAFETY.md`.
