# Text Margin Lines Tool User Guide

![Text margin lines flow](../../assets/demo/text-margin-lines.gif)

## Why

Agents sometimes need consistent left and right margins around line-oriented
observations before formatting a handoff. **multi-bot-agentic** includes
`text_margin_lines` as a deterministic, allowlisted helper that is safe for
GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.

Unlike `text_center_lines` or width-based padding, this tool adds exact,
independent margins without measuring or reflowing line content.

## Usage

Programmatic arguments:

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.text_margin_lines import TextMarginLinesTool

result = TextMarginLinesTool().execute(
    ToolInvocation(
        tool_name="text_margin_lines",
        arguments={
            "text": "GPT-5.5\nClaude Sonnet 4.6",
            "left": 2,
            "right": 1,
            "skip_first": False,
        },
    )
)
print(result.content)
```

Via the decision-engine directive:

```text
TOOL:text_margin_lines:heading
Gemini 3.x<<<TEXT_MARGIN_LINES>>>2:1:true
```

The sentinel suffix must be `left:right:skip_first`. An empty suffix uses zero
margins and `skip_first=false`.

## Behavior

Each non-empty line receives exactly `left` leading and `right` trailing ASCII
spaces. Existing whitespace is retained. Whitespace-only lines and original
line endings are preserved. With `skip_first=true`, the first line is unchanged.
Kimi K2 and other model labels are treated as ordinary text. Empty, oversized,
duplicate-sentinel, out-of-range margin, invalid boolean, and oversized-output
requests return `ok=False`.

Metadata includes both margins, `skip_first`, line counts, and input/output
character counts.

## Bounds

| Limit | Value |
|---|---|
| Max input/output chars | 20_000 |
| Left margin range | 0..200 |
| Right margin range | 0..200 |
| Default margins | 0 left, 0 right |
| Default skip_first | false |
| Network access | none |

## Safety

Listed in `SafetyPolicy.allowed_tools` as `text_margin_lines`. It uses only
bounded stdlib string operations, with no network or code execution. See
`docs/SAFETY.md`.
