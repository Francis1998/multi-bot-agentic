# Text Dedent Tool User Guide

![Text dedent flow](../../assets/demo/text-dedent.gif)

## Why

Agents often receive indented code blocks, templates, or quoted observations
that need their common leading whitespace removed without changing inner
indentation. **multi-bot-agentic** includes `text_dedent` as a deterministic,
allowlisted stdlib `textwrap` transform that is safe for GPT-5.5 / Claude
Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.

## Usage

Programmatic arguments:

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.text_dedent import TextDedentTool

result = TextDedentTool().execute(
    ToolInvocation(
        tool_name="text_dedent",
        arguments={"text": "    first\n      nested\n", "strip": True},
    )
)
print(result.content)
```

Via the decision-engine directive (single payload + sentinel):

```text
TOOL:text_dedent:    first
      nested
<<<TEXT_DEDENT>>>false
```

The sentinel suffix accepts `true`/`false`, `1`/`0`, `yes`/`no`, or
`on`/`off`. An omitted or empty suffix uses the default `strip=true`.

## Behavior

The tool applies `textwrap.dedent` to remove whitespace shared by every
non-blank line. With the default `strip=true`, outer whitespace is then
removed with `str.strip()`. Set `strip=false` to preserve outer blank lines
and trailing newlines after dedenting.

Empty, oversized, duplicate-sentinel, and invalid `strip` inputs return
`ok=False`.

## Bounds

| Limit | Value |
|---|---|
| Max text chars | 20_000 |
| Default strip | true |
| Network access | none |

## Safety

Listed in `SafetyPolicy.allowed_tools` as `text_dedent`. It uses only stdlib
`textwrap`, with no network or code execution. See `docs/SAFETY.md`.
