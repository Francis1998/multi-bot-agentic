# mime_multipart_flatten Tool Guide

![mime_multipart_flatten demo](../../assets/demo/mime-multipart-flatten.gif)

Recursively flatten nested multipart MIME into leaf metadata for GPT-6 Astra /
Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro workers. Inspired by email agent
pipelines in popular frameworks.

## Usage

```python
tool.execute(ToolInvocation(tool_name="mime_multipart_flatten", arguments={"raw": mime_text}))
```

## Bounds & Safety

- Max 20_000 chars, 200 leaf parts
- Returns content_type/filename/content_id/size/depth only — no payloads
- Never executes code or makes network requests
