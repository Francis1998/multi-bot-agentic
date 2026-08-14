# Text Outdent Tool User Guide

![Text outdent flow](../../assets/demo/text-outdent.gif)

## Why

Agents sometimes need a fixed amount of indentation removed from pasted code,
templates, or quoted observations. **multi-bot-agentic** includes
`text_outdent` as a deterministic, allowlisted helper that is safe for GPT-5.5 /
Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.

This differs from `text_dedent`, which removes the common whitespace prefix
across the block, and `text_indent`, which adds spaces. `text_outdent` removes
up to a requested number of leading ASCII spaces independently on each line.

## Usage

Programmatic arguments:

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.text_outdent import TextOutdentTool

result = TextOutdentTool().execute(
    ToolInvocation(
        tool_name="text_outdent",
        arguments={"text": "    alpha\n  beta\n", "spaces": 2, "skip_first": False},
    )
)
print(result.content)
```

Via the decision-engine directive:

```text
TOOL:text_outdent:    alpha
    beta<<<TEXT_OUTDENT>>>4:true
```

The sentinel suffix is `N` (spaces only) or `N:true`/`N:false` (spaces plus
`skip_first`). An omitted or empty suffix uses `spaces=2` and
`skip_first=false`.

## Behavior

Each non-empty line loses `min(N, leading ASCII spaces)` characters. Tabs are
never removed. Blank lines, including whitespace-only lines, and original line
endings are preserved. With `skip_first=true`, the first line is unchanged.
Empty, oversized, duplicate-sentinel, out-of-range `spaces`, and invalid
boolean inputs return `ok=False`.

## Bounds

| Limit | Value |
|---|---|
| Max text chars | 20_000 |
| Default spaces | 2 |
| Spaces range | 0..32 |
| Default skip_first | false |
| Network access | none |

## Safety

Listed in `SafetyPolicy.allowed_tools` as `text_outdent`. It uses only bounded
stdlib string operations, with no network or code execution. See
`docs/SAFETY.md`.
