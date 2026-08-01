# MIME Multipart Tool User Guide

![MIME multipart flow](../../assets/demo/mime-multipart.gif)

## Why

Agents sometimes receive raw email or HTTP multipart bodies — pasted webhook
payloads, relayed MIME messages, or attachment previews — and need a structured
summary of each part before choosing a parser. Guessing boundaries in-model is
unreliable. **multi-bot-agentic** includes `mime_multipart` as a deterministic,
allowlisted parser via stdlib `email` that is safe for GPT-5.5 / Claude Sonnet
4.6 / Gemini 3.x / Kimi K2 workers.

## Usage

Programmatic:

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.mime_multipart import MimeMultipartTool

raw = """MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="BOUNDARY"

--BOUNDARY
Content-Type: text/plain; charset=utf-8

Hello Kimi K2
--BOUNDARY--
"""
result = MimeMultipartTool().execute(
    ToolInvocation(tool_name="mime_multipart", arguments={"raw": raw})
)
print(result.content)
```

Via the decision-engine directive:

```text
TOOL:mime_multipart:<raw MIME message>
```

## Behavior

The tool parses the raw message and returns canonical JSON listing each payload
part with:

- `index`
- `content_type`
- `charset`
- `size` (decoded payload bytes)
- `payload_preview` (first 120 UTF-8 characters, replacement on errors)

Non-multipart messages return a single-part summary. Metadata includes
`part_count`, `multipart`, and input `chars`.

Empty or oversized input returns `ok=False` structured failures.

## Bounds

| Limit | Value |
|---|---|
| Max raw chars | 20_000 |
| Payload preview chars | 120 |
| Network access | none |

## Safety

Listed in `SafetyPolicy.allowed_tools` as `mime_multipart`. No network, no code
execution, no attachment extraction to disk. See `docs/SAFETY.md`.
