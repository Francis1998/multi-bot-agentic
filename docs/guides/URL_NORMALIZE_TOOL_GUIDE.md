# url_normalize Tool Guide

![url_normalize demo](../../assets/demo/url-normalize.gif)

Canonicalize URLs (scheme/host case, default ports, fragments) before the next
GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 turn.

## Why

Agent pipelines reconcile duplicate URLs that differ only by `:443`, trailing
slashes, or `#fragments`. Models mishandle edge cases; `url_normalize` uses
stdlib `urllib.parse` only (inspired by urllib3 / scrapy URL canonicalizers).

## Usage

```python
tool.execute(
    ToolInvocation(
        tool_name="url_normalize",
        arguments={
            "url": "HTTPS://Example.COM:443/docs/#top",
            "strip_trailing_slash": True,
        },
    )
)
```

## Bounds & Safety

- Required: `url` (max 8000 chars, must include scheme + host)
- Optional: `strip_trailing_slash` (default true)
- Never executes code or makes network requests
