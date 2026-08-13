# Text Indent Tool User Guide

![Text indent flow](../../assets/demo/text-indent.gif)

## Why

Agents often need every non-empty line of a pasted block indented before nesting
it in a code fence, YAML list, or quoted reply. **multi-bot-agentic** includes
`text_indent` as a deterministic, allowlisted indent helper that is safe for
GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.

## Usage

Programmatic arguments:

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.text_indent import TextIndentTool

result = TextIndentTool().execute(
    ToolInvocation(
        tool_name="text_indent",
        arguments={"text": "alpha\n\nbeta\n", "spaces": 2, "skip_first": False},
    )
)
print(result.content)
```

Via the decision-engine directive (single payload + sentinel):

```text
TOOL:text_indent:alpha
beta<<<TEXT_INDENT>>>4:true
```

The sentinel suffix is `N` (spaces only) or `N:true`/`N:false` (spaces plus
`skip_first`). An omitted or empty suffix uses `spaces=2` and
`skip_first=false`.

## Behavior

Every non-empty line receives `spaces` leading ASCII spaces. Blank lines are
left unchanged. With `skip_first=true`, the first line is not indented. Empty,
oversized, duplicate-sentinel, out-of-range `spaces`, and invalid boolean
inputs return `ok=False`.

## Bounds

| Limit | Value |
|---|---|
| Max text chars | 20_000 |
| Default spaces | 2 |
| Spaces range | 0..32 |
| Default skip_first | false |
| Network access | none |

## Safety

Listed in `SafetyPolicy.allowed_tools` as `text_indent`. It uses only stdlib
string operations, with no network or code execution. See `docs/SAFETY.md`.
