# Text Pad Lines Tool User Guide

![Text pad lines flow](../../assets/demo/text-pad-lines.gif)

## Why

Agents sometimes need each non-empty line padded to a fixed column width before
aligning code blocks, tables, or quoted observations. **multi-bot-agentic**
includes `text_pad_lines` as a deterministic, allowlisted helper that is safe
for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.

This differs from `text_wrap`, which reflows long lines, and from `text_indent`,
which prepends a fixed prefix. `text_pad_lines` expands shorter non-empty lines
to a target width with ASCII spaces.

## Usage

Programmatic arguments:

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.text_pad_lines import TextPadLinesTool

result = TextPadLinesTool().execute(
    ToolInvocation(
        tool_name="text_pad_lines",
        arguments={"text": "alpha\nbeta\n", "width": 8, "side": "right", "skip_first": False},
    )
)
print(result.content)
```

Via the decision-engine directive:

```text
TOOL:text_pad_lines:alpha
beta<<<TEXT_PAD_LINES>>>8:left:true
```

The sentinel suffix is `width`, `width:side`, `width:skip_first`, or
`width:side:skip_first`. An omitted or empty suffix uses `width=80`,
`side=right`, and `skip_first=false`.

## Behavior

Each non-empty line is padded to `width` with ASCII spaces on the requested
side (`left`, `right`, or `both`). Lines already at or above the width are
unchanged. Blank lines, including whitespace-only lines, and original line
endings are preserved. With `skip_first=true`, the first line is unchanged.
Empty, oversized, duplicate-sentinel, out-of-range `width`, invalid `side`, and
invalid boolean inputs return `ok=False`.

## Bounds

| Limit | Value |
|---|---|
| Max text chars | 20_000 |
| Default width | 80 |
| Width range | 1..200 |
| Default side | right |
| Allowed sides | left, right, both |
| Default skip_first | false |
| Network access | none |

## Safety

Listed in `SafetyPolicy.allowed_tools` as `text_pad_lines`. It uses only bounded
stdlib string operations, with no network or code execution. See
`docs/SAFETY.md`.
