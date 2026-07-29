# TSV Format Tool User Guide

![TSV format flow](../../assets/demo/tsv-format.gif)

## Why

Agent toolkits (LangChain tools, CrewAI helpers, OpenAI/Anthropic agent demos)
routinely exchange tab-separated spreadsheets for model handoffs. Pasting TSV
into prompts is error-prone (ragged columns, mixed line endings, stray blank
rows). **multi-bot-agentic** includes `tsv_format` as a deterministic,
allowlisted formatter that is safe for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x /
Kimi K2 workers.

## Usage

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.tsv_format import TsvFormatTool

result = TsvFormatTool().execute(
    ToolInvocation(
        tool_name="tsv_format",
        arguments={
            "text": """model\tscore
GPT-5.5\t95
Claude Sonnet 4.6\t92
Gemini 3.x\t90
"""
        },
    )
)
print(result.content)
```

Via the decision-engine directive:

```text
TOOL:tsv_format:model	score
GPT-5.5	95
Kimi K2	88
```

## Behavior

Parsing uses the stdlib `csv` module with the `excel-tab` dialect (tab
delimiter, Excel-style quoting). The tool:

- treats the first row as the header that defines column width;
- rejects rows whose column count differs from the header;
- strips trailing blank rows;
- re-serializes with `\n` line endings and no trailing blank line.

Empty documents, oversized input, malformed CSV/TSV, and ragged tables return
`ok=False` structured failures instead of being evaluated.

## Bounds

| Limit | Value |
|---|---|
| Max document chars | 20_000 |
| Delimiter | Tab (`excel-tab`) |
| Column width | Defined by header row |
| Parse runtime | stdlib `csv` only |

## Safety

Listed in `SafetyPolicy.allowed_tools` as `tsv_format`. No network, no code
execution, and no constructor hooks. See `docs/SAFETY.md`.
