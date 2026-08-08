# CSV Filter Tool User Guide

![CSV filter flow](../../assets/demo/csv-filter.gif)

## Why

Agents routinely need to keep only the CSV rows that match a named-column
predicate before the next LLM turn. Filtering in-model can drop quoted cells,
shift columns, or invent rows. **multi-bot-agentic** includes `csv_filter` as a
deterministic, allowlisted equals/contains filter via stdlib `csv` that is safe
for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.

## Usage

Programmatic arguments:

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.csv_filter import CsvFilterTool

result = CsvFilterTool().execute(
    ToolInvocation(
        tool_name="csv_filter",
        arguments={
            "text": "id,status\n1,open\n2,closed\n3,OPEN\n",
            "column": "status",
            "value": "open",
            "mode": "equals",
            "case_insensitive": True,
        },
    )
)
print(result.content)
```

Via the decision-engine directive (single payload + sentinel):

```text
TOOL:csv_filter:id,status
1,open
2,closed
<<<CSV_FILTER>>>status<<<=>>>open
```

Use `column<<<~>>>value` for substring matching:

```text
TOOL:csv_filter:id,title
1,urgent bug
2,feature
<<<CSV_FILTER>>>title<<<~>>>bug
```

## Behavior

- `mode="equals"` (default): selected cell must equal `value`
- `mode="contains"`: selected cell must contain `value`
- `case_insensitive=True` by default; set false for case-sensitive matching
- Output preserves the header and writes only matching rows as canonical CSV
- No matches still return a valid CSV containing just the header
- Metadata includes `rows_in`, `rows_out`, and `column`

Unknown columns, invalid modes, malformed CSV, oversized input, and row/column
overages return `ok=False` structured failures.

## Bounds

| Limit | Value |
|---|---|
| Max text chars | 20_000 |
| Max rows | 500 |
| Max columns | 64 |
| Network access | none |

## Safety

Listed in `SafetyPolicy.allowed_tools` as `csv_filter`. No network, no code
execution. Parsing and serialization use only the Python stdlib `csv` module.
See `docs/SAFETY.md`.
