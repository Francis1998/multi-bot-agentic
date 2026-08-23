# mime_multipart_flatten Tool Guide

![mime_multipart_flatten demo](../../assets/demo/mime-multipart-flatten.gif)

Recursively flatten nested multipart MIME into leaf metadata for GPT-5.5 /
Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers. Inspired by email agent
pipelines in popular frameworks.

## Usage

```python
tool.execute(ToolInvocation(tool_name="mime_multipart_flatten", arguments={"raw": mime_text}))
```

## Bounds & Safety

- Max 20_000 chars, 200 leaf parts
- Returns content_type/filename/content_id/size/depth only — no payloads
- Never executes code or makes network requests
