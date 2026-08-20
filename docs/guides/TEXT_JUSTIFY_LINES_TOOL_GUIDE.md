# Text Justify Lines Tool User Guide

![Text justify lines flow](../../assets/demo/text-justify-lines.gif)

## Why

Agents sometimes need stable fixed-width lines without relying on a model to
count columns or distribute whitespace. **multi-bot-agentic** includes
`text_justify_lines` as a deterministic, allowlisted formatter that is safe for
GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.

It combines left, right, and center alignment with full justification, while
`text_center_lines` and `text_pad_lines` cover narrower padding-only workflows.

## Usage

Programmatic arguments:

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.text_justify_lines import TextJustifyLinesTool

result = TextJustifyLinesTool().execute(
    ToolInvocation(
        tool_name="text_justify_lines",
        arguments={
            "text": "GPT-5.5 Claude Sonnet 4.6\nGemini 3.x Kimi K2",
            "width": 40,
            "alignment": "justify",
            "skip_first": False,
        },
    )
)
print(result.content)
```

`align` and `mode` are accepted aliases for `alignment`.

Via the decision-engine directive:

```text
TOOL:text_justify_lines:heading
Gemini 3.x Kimi K2<<<TEXT_JUSTIFY_LINES>>>30:justify:true
```

The sentinel suffix is `width[:alignment[:skip_first]]`. An empty suffix uses
width 80, left alignment, and `skip_first=false`.

## Behavior

`left`, `right`, and `center` add ASCII spaces until each non-empty line reaches
the target width. Lines already at or above the width are unchanged.
`justify` splits a line into whitespace-delimited words and distributes spaces
across its gaps, placing indivisible extra spaces in leftmost gaps. A single
word is left-aligned. Content that cannot fit is never truncated.

Whitespace-only lines and original line endings are preserved. `skip_first`
leaves the first line unchanged. Invalid, empty, oversized, duplicate-sentinel,
and oversized-output requests return `ok=False`.

## Bounds

| Limit | Value |
|---|---|
| Max input/output chars | 20,000 |
| Width range | 1..500 |
| Default width | 80 |
| Alignments | `left`, `right`, `center`, `justify` |
| Default alignment | `left` |
| Network access | none |

## Safety

Listed in `SafetyPolicy.allowed_tools` as `text_justify_lines`. It uses bounded
stdlib string operations only, with no network, file access, or code execution.
See `docs/SAFETY.md`.
