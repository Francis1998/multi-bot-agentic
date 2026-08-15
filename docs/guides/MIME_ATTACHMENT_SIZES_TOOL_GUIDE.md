# MIME Attachment Sizes Tool User Guide

![MIME attachment sizes flow](../../assets/demo/mime-attachment-sizes.gif)

## Why

Agents sometimes need attachment byte sizes for routing or quota checks without
copying message bodies or attachment bytes into another model turn.
**multi-bot-agentic** includes `mime_attachment_sizes` as a deterministic,
allowlisted stdlib `email` parser that is safe for GPT-5.5 / Claude Sonnet 4.6 /
Gemini 3.x / Kimi K2 workers.

Unlike `mime_attachment_names`, this tool emits filename/size objects instead
of filenames alone. Unlike `mime_multipart`, it never returns payload previews.

## Usage

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.mime_attachment_sizes import MimeAttachmentSizesTool

raw = """MIME-Version: 1.0
Content-Type: application/pdf
Content-Disposition: attachment; filename="report.pdf"
Content-Length: 128

Private payload
"""
result = MimeAttachmentSizesTool().execute(ToolInvocation(tool_name="mime_attachment_sizes", arguments={"raw": raw}))
print(result.content)
```

Via the decision-engine directive:

```text
TOOL:mime_attachment_sizes:<raw MIME message>
```

## Behavior

The result is a JSON list of `{"filename": "...", "size": N}` objects in MIME
traversal order. Standard `Content-Disposition` `filename` parameters are
preferred, with `Content-Type` `name` parameters used as the stdlib fallback.
`size` uses the part's `Content-Length` header when present, otherwise the
decoded payload byte length. A valid message without named attachments returns
`[]`. Empty, oversized, or structurally defective input returns `ok=False`.

Metadata includes `attachment_count`, child `part_count`, and input `chars`.

## Bounds

| Limit | Value |
|---|---|
| Max raw chars | 20_000 |
| Payload content returned | none |
| Network access | none |

## Safety

Listed in `SafetyPolicy.allowed_tools` as `mime_attachment_sizes`. It uses only
stdlib `email`, with no network, code execution, payload decoding, or attachment
writes. See `docs/SAFETY.md`.
