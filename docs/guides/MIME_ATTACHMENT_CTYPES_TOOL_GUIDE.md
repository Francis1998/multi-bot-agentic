# MIME Attachment Content Types Tool User Guide

![MIME attachment content types flow](../../assets/demo/mime-attachment-ctypes.gif)

## Why

Agents sometimes need attachment media types for routing without copying
message bodies or attachment bytes into another model turn.
**multi-bot-agentic** includes `mime_attachment_ctypes` as a deterministic,
allowlisted stdlib `email` parser that is safe for GPT-5.5 /
Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.

Unlike `mime_attachment_names`, this tool emits filename/content-type objects.
Unlike `mime_multipart`, it never returns payload previews.

## Usage

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.mime_attachment_ctypes import MimeAttachmentCtypesTool

raw = """MIME-Version: 1.0
Content-Type: application/pdf
Content-Disposition: attachment; filename="report.pdf"

Private payload
"""
result = MimeAttachmentCtypesTool().execute(ToolInvocation(tool_name="mime_attachment_ctypes", arguments={"raw": raw}))
print(result.content)
```

Via the decision-engine directive:

```text
TOOL:mime_attachment_ctypes:<raw MIME message>
```

## Behavior

The result is a JSON list of
`{"filename": "...", "content_type": "type/subtype"}` objects in MIME traversal
order. Standard `Content-Disposition` `filename` parameters are preferred, with
`Content-Type` `name` parameters used as the stdlib fallback. The media type is
read from the part's `Content-Type` header; a missing header produces
`application/octet-stream`. A valid message without named attachments returns
`[]`. Empty, oversized, or structurally defective input returns `ok=False`.

Metadata includes `attachment_count`, child `part_count`, and input `chars`.

## Bounds

| Limit | Value |
|---|---|
| Max raw chars | 20_000 |
| Missing Content-Type | `application/octet-stream` |
| Payload content returned | none |
| Network access | none |

## Safety

Listed in `SafetyPolicy.allowed_tools` as `mime_attachment_ctypes`. It uses only
stdlib `email`, with no network, code execution, payload decoding, or attachment
writes. See `docs/SAFETY.md`.
