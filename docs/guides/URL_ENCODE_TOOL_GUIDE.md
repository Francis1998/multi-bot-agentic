# URL Encode Tool User Guide

![URL encode flow](../../assets/demo/url-encode.gif)

## Why

Agents often need a stable percent-encoded path segment, query value, or token
before composing a URL. **multi-bot-agentic** includes `url_encode` as a
deterministic, allowlisted `urllib.parse.quote` wrapper that is safe for GPT-5.5
/ Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.

## Usage

Programmatic arguments:

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.url_encode import UrlEncodeTool

result = UrlEncodeTool().execute(
    ToolInvocation(
        tool_name="url_encode",
        arguments={"text": "a b/c", "safe": "/", "plus": False},
    )
)
print(result.content)
```

Via the decision-engine directive (single payload + sentinel):

```text
TOOL:url_encode:a b<<<URL_ENCODE>>>true
```

or with key=value options:

```text
TOOL:url_encode:path/to<<<URL_ENCODE>>>safe=:plus=true
```

A bare boolean sentinel suffix sets `plus`. An omitted or empty suffix uses
`safe="/"` and `plus=false`.

## Behavior

By default the tool calls `urllib.parse.quote` with `safe="/"`. When
`plus=true`, it uses `urllib.parse.quote_plus` so spaces become `+`. Empty,
oversized, duplicate-sentinel, and invalid `plus` inputs return `ok=False`.

## Bounds

| Limit | Value |
|---|---|
| Max text chars | 20_000 |
| Default safe | `/` |
| Default plus | false |
| Network access | none |

## Safety

Listed in `SafetyPolicy.allowed_tools` as `url_encode`. It uses only stdlib
`urllib.parse`, with no network or code execution. See `docs/SAFETY.md`.
