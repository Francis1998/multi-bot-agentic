# HTML Table CSV Tool User Guide

![HTML table CSV flow](../../assets/demo/html-table-csv.gif)

## Why

Agents routinely receive tabular data wrapped in HTML — documentation tables,
email digests, dashboard snippets, and scraped pages. Letting a model transcribe
those tables into CSV can shift cells, miss entities, or overrun the event log.
**multi-bot-agentic** includes `html_table_csv` as a deterministic,
allowlisted converter that is safe for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x /
Kimi K2 workers.

## Usage

Programmatic:

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.html_table_csv import HtmlTableCsvTool

result = HtmlTableCsvTool().execute(
    ToolInvocation(
        tool_name="html_table_csv",
        arguments={
            "text": "<table><tr><th>model</th><th>score</th></tr><tr><td>GPT-5.5</td><td>98</td></tr></table>",
        },
    )
)
print(result.content)
```

Convert every table in a document:

```python
result = HtmlTableCsvTool().execute(
    ToolInvocation(
        tool_name="html_table_csv",
        arguments={
            "text": "<table><tr><th>a</th></tr><tr><td>1</td></tr></table><table><tr><th>b</th></tr><tr><td>Kimi K2</td></tr></table>",
            "all": True,
        },
    )
)
```

Via the decision-engine directive:

```text
TOOL:html_table_csv:<table><tr><th>model</th></tr><tr><td>Claude Sonnet 4.6</td></tr></table>
```

## Behavior

- default `all=false` converts only the first `<table>`;
- `all=true` emits one CSV block per table, separated by a blank line;
- cell text is entity-decoded, trimmed, and normalized;
- ragged rows are padded to the widest row in each table.

Empty input, missing tables, oversized documents/output, and documents
containing `<script>` or `<style>` return `ok=False` structured failures.

## Bounds

| Limit | Value |
|---|---|
| Max document chars | 20_000 |
| Max output chars | 20_000 |
| Rejected tags | `script`, `style` |
| Parse runtime | stdlib `html.parser` and `csv` only |

## Safety

Listed in `SafetyPolicy.allowed_tools` as `html_table_csv`. No network, no code
execution, no extraction of archive members. See `docs/SAFETY.md`.
