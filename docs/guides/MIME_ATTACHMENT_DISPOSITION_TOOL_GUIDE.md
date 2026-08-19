# MIME Attachment Disposition Tool User Guide

![MIME attachment disposition flow](../../assets/demo/mime-attachment-disposition.gif)

## Why

Agents sometimes need to distinguish attachment and inline MIME parts without
copying message bodies or attachment bytes into another model turn.
**multi-bot-agentic** includes `mime_attachment_disposition` as a deterministic,
allowlisted stdlib `email` parser that is safe for GPT-5.5 /
Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.

Unlike `mime_attachment_names`, this tool emits only values declared by
Content-Disposition and retains disposition records that have no filename.

## Usage

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.mime_attachment_disposition import (
    MimeAttachmentDispositionTool,
)

raw = """MIME-Version: 1.0
Content-Type: application/pdf
Content-Disposition: attachment; filename="report.pdf"

Private payload
"""
result = MimeAttachmentDispositionTool().execute(
    ToolInvocation(tool_name="mime_attachment_disposition", arguments={"raw": raw})
)
print(result.content)
```

Via the decision-engine directive:

```text
TOOL:mime_attachment_disposition:<raw MIME message>
```

## Behavior

The result is a JSON list of
`{"filename": "...", "disposition": "attachment"}` objects in MIME traversal
order. Inline parts report `inline`. A disposition without a filename reports
`null`; a Content-Type `name` parameter without Content-Disposition is omitted.
RFC-encoded filename parameters are decoded by the stdlib email policy. A valid
message without disposition headers returns `[]`. Empty, oversized, or
structurally defective input returns `ok=False`.

Metadata includes `disposition_count`, child `part_count`, and input `chars`.

## Bounds

| Limit | Value |
|---|---|
| Max raw chars | 20_000 |
| Payload content returned | none |
| Parser | Python stdlib `email` only |
| Network access | none |

## Safety

Listed in `SafetyPolicy.allowed_tools` as `mime_attachment_disposition`. It uses
only stdlib `email`, with no network, code execution, payload decoding, or
attachment writes. See `docs/SAFETY.md`.
