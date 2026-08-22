# MIME Attachment CID Map Tool User Guide

![MIME attachment CID map flow](../../assets/demo/mime-attachment-cid-map.gif)

## Why

Agents sometimes need to resolve `cid:` references in multipart messages to
attachment filenames and content types without copying payloads into the next
turn. **multi-bot-agentic** includes `mime_attachment_cid_map` as a
deterministic, allowlisted stdlib `email` parser that is safe for GPT-5.5 /
Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.

Unlike `mime_attachment_names`, `mime_attachment_ctypes`, and related tools,
this map is keyed by Content-ID rather than filename order.

## Usage

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.mime_attachment_cid_map import MimeAttachmentCidMapTool

raw = """MIME-Version: 1.0
Content-Type: multipart/related; boundary="B"

--B
Content-Type: image/png
Content-ID: <logo@gpt55>
Content-Disposition: inline; filename="logo.png"

Private PNG
--B--
"""
result = MimeAttachmentCidMapTool().execute(ToolInvocation(tool_name="mime_attachment_cid_map", arguments={"raw": raw}))
print(result.content)
```

Via the decision-engine directive:

```text
TOOL:mime_attachment_cid_map:<raw MIME message>
```

## Behavior

The result is a JSON object whose keys are Content-ID tokens with surrounding
angle brackets stripped. Each value is an object with `filename` and
`content_type`. Missing filenames become an empty string; missing Content-Type
headers default to `application/octet-stream`. Duplicate Content-ID values fail
with `ok=False`. A valid message without Content-ID headers returns `{}`.
Empty, oversized, or structurally defective input also returns `ok=False`.
Payload bytes are never included.

## Bounds

| Limit | Value |
|---|---|
| Max raw / output chars | 20,000 |
| Payload content returned | none |
| Files written | none |
| Network access | none |

## Safety

Listed in `SafetyPolicy.allowed_tools` as `mime_attachment_cid_map`. It uses
only stdlib `email` and `json`, with no network, code execution, payload
decoding, or attachment writes. See `docs/SAFETY.md`.
