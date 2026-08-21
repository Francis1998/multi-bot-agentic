# MIME Attachment Filenames Unique Tool User Guide

![MIME attachment unique filenames flow](../../assets/demo/mime-attachment-filenames-unique.gif)

## Why

Agents sometimes need collision-free destination names when a MIME message
contains repeated attachment filenames. **multi-bot-agentic** includes
`mime_attachment_filenames_unique` as a deterministic, allowlisted stdlib
`email` parser that is safe for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x /
Kimi K2 workers.

Unlike `mime_attachment_names`, this tool groups each decoded original name and
assigns one unique name per occurrence. It never returns attachment payloads.

## Usage

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.mime_attachment_filenames_unique import (
    MimeAttachmentFilenamesUniqueTool,
)

raw = """MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="B"

--B
Content-Disposition: attachment; filename="report.pdf"

Private payload
--B
Content-Disposition: attachment; filename="report.pdf"

Another private payload
--B--
"""
result = MimeAttachmentFilenamesUniqueTool().execute(
    ToolInvocation(tool_name="mime_attachment_filenames_unique", arguments={"raw": raw})
)
print(result.content)
```

Via the decision-engine directive:

```text
TOOL:mime_attachment_filenames_unique:<raw MIME message>
```

## Behavior

The result is a JSON object whose keys are decoded original filenames and whose
values are arrays containing one collision-free name per MIME occurrence. An
array is necessary because JSON cannot represent repeated object keys. For
example, three `report.pdf` attachments map to:

```json
{
  "report.pdf": ["report.pdf", "report-2.pdf", "report-3.pdf"]
}
```

The first occurrence keeps its name. Later occurrences receive `-2`, `-3`, and
so on before the final extension. Generated names skip other original names, so
the full output remains unique. A valid message without named attachments
returns `{}`. Empty, oversized, or structurally defective input returns
`ok=False`.

## Bounds

| Limit | Value |
|---|---|
| Max raw / output chars | 20,000 |
| Payload content returned | none |
| Files written | none |
| Network access | none |

## Safety

Listed in `SafetyPolicy.allowed_tools` as
`mime_attachment_filenames_unique`. It uses only stdlib `email`, `json`, and
filename string handling, with no network, code execution, payload decoding, or
attachment writes. See `docs/SAFETY.md`.
