# MIME Attachment Names Tool User Guide

![MIME attachment names flow](../../assets/demo/mime-attachment-names.gif)

## Why

Agents sometimes need attachment names for routing without copying message
bodies or attachment bytes into another model turn. **multi-bot-agentic**
includes `mime_attachment_names` as a deterministic, allowlisted stdlib
`email` parser that is safe for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x /
Kimi K2 workers.

Unlike `mime_part_headers`, this tool emits a compact list instead of complete
header maps. It never returns payload content.

## Usage

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.mime_attachment_names import MimeAttachmentNamesTool

raw = """MIME-Version: 1.0
Content-Type: application/pdf
Content-Disposition: attachment; filename="report.pdf"

Private payload
"""
result = MimeAttachmentNamesTool().execute(ToolInvocation(tool_name="mime_attachment_names", arguments={"raw": raw}))
print(result.content)
```

Via the decision-engine directive:

```text
TOOL:mime_attachment_names:<raw MIME message>
```

## Behavior

The result is a JSON list of decoded filenames in MIME traversal order.
Standard `Content-Disposition` `filename` parameters are preferred, with
`Content-Type` `name` parameters used as the stdlib fallback. A valid message
without named attachments returns `[]`. Empty, oversized, or structurally
defective input returns `ok=False`.

Metadata includes `attachment_count`, child `part_count`, and input `chars`.

## Bounds

| Limit | Value |
|---|---|
| Max raw chars | 20_000 |
| Payload content returned | none |
| Network access | none |

## Safety

Listed in `SafetyPolicy.allowed_tools` as `mime_attachment_names`. It uses only
stdlib `email`, with no network, code execution, payload decoding, or attachment
writes. See `docs/SAFETY.md`.
