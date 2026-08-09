# CSV Select Columns Tool User Guide

![CSV select columns flow](../../assets/demo/csv-select-columns.gif)

## Why

Agents often need only a subset of CSV columns — or a stable column order —
before the next LLM turn. Projecting tables in-model can drop quoted cells or
scramble headers. **multi-bot-agentic** includes `csv_select_columns` as a
deterministic, allowlisted column projector via stdlib `csv` that is safe for
GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.

## Usage

Programmatic arguments:

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.csv_select_columns import CsvSelectColumnsTool

result = CsvSelectColumnsTool().execute(
    ToolInvocation(
        tool_name="csv_select_columns",
        arguments={
            "text": "id,name,status\n1,Ada,open\n2,Grace,closed\n",
            "columns": ["status", "id"],
        },
    )
)
print(result.content)
```

Via the decision-engine directive (single payload + sentinel):

```text
TOOL:csv_select_columns:id,name,status
1,Ada,open
<<<CSV_SELECT>>>status,id
```

`columns` may also be a comma-separated string.

## Behavior

- Emits CSV with only the requested columns, in the requested order
- Preserves body row order and quoted-cell fidelity via stdlib `csv`
- Metadata includes `rows`, `columns`, and `column_count`
- Unknown, duplicate, or empty column names return `ok=False`
- Empty, oversized, malformed, and row/column overages return `ok=False`

## Bounds

| Limit | Value |
|---|---|
| Max text chars | 20_000 |
| Max rows | 500 |
| Max columns | 64 |
| Network access | none |

## Safety

Listed in `SafetyPolicy.allowed_tools` as `csv_select_columns`. No network, no
code execution. Parsing and serialization use only the Python stdlib `csv`
module. See `docs/SAFETY.md`.
