# Text Center Lines Tool User Guide

![Text center lines flow](../../assets/demo/text-center-lines.gif)

## Why

Agents sometimes need each non-empty line centered to a fixed column width
before aligning headings, code blocks, or quoted observations.
**multi-bot-agentic** includes `text_center_lines` as a deterministic,
allowlisted helper that is safe for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x /
Kimi K2 workers.

This differs from `text_wrap`, which reflows long lines, and from
`text_pad_lines`, which exposes left/right/both placement. `text_center_lines`
always distributes ASCII spaces across both sides.

## Usage

Programmatic arguments:

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.text_center_lines import TextCenterLinesTool

result = TextCenterLinesTool().execute(
    ToolInvocation(
        tool_name="text_center_lines",
        arguments={"text": "alpha\nbeta\n", "width": 8, "skip_first": False},
    )
)
print(result.content)
```

Via the decision-engine directive:

```text
TOOL:text_center_lines:heading
body<<<TEXT_CENTER_LINES>>>10:true
```

The sentinel suffix is `width` or `width:skip_first`. An omitted or empty
suffix uses `width=80` and `skip_first=false`.

## Behavior

Each non-empty line shorter than `width` is centered with ASCII spaces. When an
odd number of spaces is needed, the extra space is placed on the right. Lines
already at or above the width are unchanged. Blank lines, including
whitespace-only lines, and original line endings are preserved. With
`skip_first=true`, the first line is unchanged. Empty, oversized,
duplicate-sentinel, out-of-range `width`, invalid boolean, and oversized-output
inputs return `ok=False`.

## Bounds

| Limit | Value |
|---|---|
| Max input/output chars | 20_000 |
| Default width | 80 |
| Width range | 1..200 |
| Padding placement | both sides |
| Default skip_first | false |
| Network access | none |

## Safety

Listed in `SafetyPolicy.allowed_tools` as `text_center_lines`. It uses only
bounded stdlib string operations, with no network or code execution. See
`docs/SAFETY.md`.
