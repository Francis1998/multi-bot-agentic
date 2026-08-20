# MIME Attachment Encoding Tool User Guide

![MIME attachment encoding flow](../../assets/demo/mime-attachment-encoding.gif)

## Why

Agents sometimes need to route or validate MIME attachments by transfer
encoding without exposing message bodies or attachment bytes.
**multi-bot-agentic** includes `mime_attachment_encoding` as a deterministic,
allowlisted stdlib `email` parser that is safe for GPT-5.5 /
Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.

It complements `mime_attachment_names`, `mime_attachment_ctypes`,
`mime_attachment_sizes`, and `mime_attachment_disposition` with
Content-Transfer-Encoding metadata.

## Usage

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.mime_attachment_encoding import (
    MimeAttachmentEncodingTool,
)

raw = """MIME-Version: 1.0
Content-Type: application/pdf
Content-Disposition: attachment; filename="report.pdf"
Content-Transfer-Encoding: base64

Private payload
"""
result = MimeAttachmentEncodingTool().execute(
    ToolInvocation(tool_name="mime_attachment_encoding", arguments={"raw": raw})
)
print(result.content)
```

Via the decision-engine directive:

```text
TOOL:mime_attachment_encoding:<raw MIME message>
```

## Behavior

The result is a JSON list such as
`{"filename": "report.pdf", "encoding": "base64"}` in MIME traversal order.
Named attachment and inline parts are included, matching the neighboring MIME
metadata tools. RFC-encoded filenames are decoded by the stdlib email policy.
Encoding tokens are normalized to lowercase; an omitted
Content-Transfer-Encoding defaults to RFC MIME value `7bit`.

Payloads are never decoded, returned, or written. Unnamed body or attachment
parts are omitted. A valid message without named parts returns `[]`. Empty,
oversized, structurally defective, or oversized-output input returns `ok=False`.

## Bounds

| Limit | Value |
|---|---|
| Max raw chars | 20,000 |
| Max output chars | 20,000 |
| Missing encoding | `7bit` |
| Payload content returned | none |
| Parser | Python stdlib `email` only |
| Network access | none |

## Safety

Listed in `SafetyPolicy.allowed_tools` as `mime_attachment_encoding`. It uses
bounded stdlib parsing only, with no payload decoding, network, file access,
attachment writes, or code execution. See `docs/SAFETY.md`.
