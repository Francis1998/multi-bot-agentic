# Markdown Table Tool User Guide

![Markdown table flow](../../assets/demo/markdown-table.gif)

## Why

Agents routinely need to present small tabular outputs in issue comments, run
summaries, and final answers. Letting a model hand-format markdown can produce
shifted columns or unescaped pipes. **multi-bot-agentic** includes
`markdown_table` as a deterministic, allowlisted renderer that is safe for
GPT-5.5 / Claude Sonnet 4.6 / Gemini 2.5 / Kimi K2 workers.

## Usage

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.markdown_table import MarkdownTableTool

result = MarkdownTableTool().execute(
    ToolInvocation(
        tool_name="markdown_table",
        arguments={"text": "name,score\nGPT-5.5,98\nKimi K2,94\n"},
    )
)
print(result.content)
```

Via the decision-engine directive:

```text
TOOL:markdown_table:name,score
GPT-5.5,98
Kimi K2,94
```

Programmatic callers can pass rows directly:

```python
MarkdownTableTool().execute(
    ToolInvocation(
        tool_name="markdown_table",
        arguments={"rows": [["model", "score"], ["Claude Sonnet 4.6", 97], ["Gemini 2.5", 96]]},
    )
)
```

## Bounds

| Limit | Value |
|---|---|
| Max document chars | 20_000 |
| Max data rows | 200 |
| Max columns | 32 |
| Default delimiter | `,` |

Cells containing `|` are escaped and embedded newlines are rendered as `<br>` so
cell content cannot break the table shape. Empty input, oversized tables,
malformed row lists, and invalid delimiters return `ok=False` structured
failures.

## Safety

Listed in `SafetyPolicy.allowed_tools` as `markdown_table`. No network, no code
execution, stdlib `csv`/`json` only. See `docs/SAFETY.md`.
