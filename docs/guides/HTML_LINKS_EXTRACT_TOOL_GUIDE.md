# html_links_extract Tool Guide

![html_links_extract demo](../../assets/demo/html-links-extract.gif)

Extract anchor `href` + text pairs as JSON before the next GPT-5.5 /
Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 research turn.

## Why

Browser-use / Scrapy-style agent pipelines need link inventories without
fetching pages or running JS. This tool is stdlib-only and bounded.

## Usage

```python
tool.execute(
    ToolInvocation(
        tool_name="html_links_extract",
        arguments={"html": '<a href="/docs">Docs</a>', "max_links": 100},
    )
)
```

## Bounds & Safety

- Max 20_000 input/output chars
- `max_links` in 1..500 (default 100)
- Rejects documents containing `script`/`style`
- Never executes code or makes network requests
