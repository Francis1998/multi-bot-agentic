# MIME Part Headers Tool User Guide

![MIME part headers flow](../../assets/demo/mime-part-headers.gif)

## Why

Agents sometimes need message routing metadata without copying email bodies or
attachments into another model turn. **multi-bot-agentic** includes
`mime_part_headers` as a deterministic, allowlisted stdlib `email` parser that
is safe for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.

Unlike `mime_multipart`, which includes a bounded payload preview for each
leaf part, this tool returns header maps only and never includes payload data.

## Usage

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.mime_part_headers import MimePartHeadersTool

raw = """Subject: Model handoff
MIME-Version: 1.0
Content-Type: multipart/alternative; boundary="BOUNDARY"

--BOUNDARY
Content-Type: text/plain; charset=utf-8

Private body
--BOUNDARY--
"""
result = MimePartHeadersTool().execute(ToolInvocation(tool_name="mime_part_headers", arguments={"raw": raw}))
print(result.content)
```

Via the decision-engine directive:

```text
TOOL:mime_part_headers:<raw MIME message>
```

## Behavior

The result is canonical JSON with:

- `top_level`: the message's header name/value map
- `parts`: each child MIME part's 1-based `index` and `headers` map
- repeated header names represented by an ordered list of values

Metadata includes `top_level_header_count`, `part_count`, and input `chars`.
Empty, oversized, or structurally malformed input returns `ok=False`.

## Bounds

| Limit | Value |
|---|---|
| Max raw chars | 20_000 |
| Payload content returned | none |
| Network access | none |

## Safety

Listed in `SafetyPolicy.allowed_tools` as `mime_part_headers`. It uses only
stdlib `email`, with no network, code execution, or attachment writes. See
`docs/SAFETY.md`.
