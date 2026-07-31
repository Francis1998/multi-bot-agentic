# ZIP List Tool User Guide

![ZIP list flow](../../assets/demo/zip-list.gif)

## Why

Agents sometimes receive small ZIP payloads as base64 blobs — export bundles,
attachment previews, or relayed tool output — and need member metadata before
choosing a parser. Extracting or executing archive contents is unsafe.
**multi-bot-agentic** includes `zip_list` as a deterministic, allowlisted
lister that is safe for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2
workers.

## Usage

Programmatic:

```python
import base64
import io
import zipfile

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.zip_list import ZipListTool

buffer = io.BytesIO()
with zipfile.ZipFile(buffer, "w") as archive:
    archive.writestr("models/gpt-5.5.txt", "GPT-5.5")
payload = base64.b64encode(buffer.getvalue()).decode("ascii")

result = ZipListTool().execute(ToolInvocation(tool_name="zip_list", arguments={"text": payload}))
print(result.content)
```

Via the decision-engine directive:

```text
TOOL:zip_list:UEsDBBQAAAAI...
```

## Behavior

- input must be standard base64-encoded ZIP bytes in the `text` argument;
- output is canonical JSON listing each member's `name`, `size`,
  `compress_size`, and `date` timestamp;
- members are sorted by name;
- the tool never extracts or executes archive contents.

Empty input, invalid base64, non-ZIP payloads, oversized base64 text, and
decoded byte payloads above the cap return `ok=False` structured failures.

## Bounds

| Limit | Value |
|---|---|
| Max base64 chars | 20_000 |
| Max decoded bytes | 20_000 |
| Extraction / execution | never |

## Safety

Listed in `SafetyPolicy.allowed_tools` as `zip_list`. No network, no extraction,
no code execution. See `docs/SAFETY.md`.
