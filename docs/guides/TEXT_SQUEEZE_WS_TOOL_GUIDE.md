# Text Squeeze Whitespace Tool User Guide

![Text squeeze whitespace flow](../../assets/demo/text-squeeze-ws.gif)

## Why

Agents often receive messy pasted observations with runs of spaces, tabs, or
newlines that waste context and break exact matches. **multi-bot-agentic**
includes `text_squeeze_ws` as a deterministic, allowlisted whitespace normalizer
that is safe for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.

## Usage

Programmatic arguments:

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.text_squeeze_ws import TextSqueezeWsTool

result = TextSqueezeWsTool().execute(
    ToolInvocation(
        tool_name="text_squeeze_ws",
        arguments={"text": "a   b\n\nc", "preserve_newlines": False},
    )
)
print(result.content)
```

Via the decision-engine directive (single payload + sentinel):

```text
TOOL:text_squeeze_ws:a   b
c  d<<<TEXT_SQUEEZE>>>true
```

The sentinel suffix accepts `true`/`false`, `1`/`0`, `yes`/`no`, or
`on`/`off`. An omitted or empty suffix uses the default
`preserve_newlines=false`.

## Behavior

With the default `preserve_newlines=false`, every whitespace run (including
newlines) collapses to a single space. With `preserve_newlines=true`, only
horizontal whitespace within each line is squeezed; newline characters are kept.
Empty, oversized, duplicate-sentinel, and invalid boolean inputs return
`ok=False`.

## Bounds

| Limit | Value |
|---|---|
| Max text chars | 20_000 |
| Default preserve_newlines | false |
| Network access | none |

## Safety

Listed in `SafetyPolicy.allowed_tools` as `text_squeeze_ws`. It uses only
stdlib `re`, with no network or code execution. See `docs/SAFETY.md`.
