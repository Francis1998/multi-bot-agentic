# Content Type Sniff Tool User Guide

![Content type sniff flow](../../assets/demo/content-type-sniff.gif)

## Why

Agents often receive opaque text blobs — pasted API responses, scraped snippets,
or relayed tool payloads — and must choose the right parser next. Guessing the
format in-model is unreliable. **multi-bot-agentic** includes `content_type_sniff`
as a deterministic, allowlisted sniffer that is safe for GPT-5.5 / Claude Sonnet
4.6 / Gemini 3.x / Kimi K2 workers.

## Usage

Programmatic:

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.content_type_sniff import ContentTypeSniffTool

result = ContentTypeSniffTool().execute(
    ToolInvocation(
        tool_name="content_type_sniff",
        arguments={"text": '{"model":"GPT-5.5","score":98}'},
    )
)
print(result.content, result.metadata["confidence"])
```

Sniff a base64 byte prefix:

```python
result = ContentTypeSniffTool().execute(
    ToolInvocation(
        tool_name="content_type_sniff",
        arguments={"bytes_base64": "eyJ2ZW5kb3IiOiJNb29uc2hvdCJ9"},
    )
)
```

Via the decision-engine directive:

```text
TOOL:content_type_sniff:<?xml version="1.0"?><root><item>Kimi K2</item></root>
```

## Behavior

Detected types: `json`, `xml`, `html`, `csv`, `tsv`, `markdown`, `plain`.

- valid JSON objects/arrays return high confidence;
- XML declarations and tag structure return `xml`;
- HTML doctypes and common tags return `html`;
- stable comma- or tab-delimited multi-line tables return `csv` or `tsv`;
- lightweight Markdown signals return `markdown`;
- otherwise the tool falls back to `plain`.

The tool returns the detected type in `content` and repeats it in metadata with
a `confidence` score between 0 and 1.

Empty or oversized input returns `ok=False` structured failures.

## Bounds

| Limit | Value |
|---|---|
| Max sample chars | 20_000 |
| Max decoded bytes (`bytes_base64`) | 20_000 |
| Network access | none |

## Safety

Listed in `SafetyPolicy.allowed_tools` as `content_type_sniff`. No network, no
code execution, no archive extraction. See `docs/SAFETY.md`.
