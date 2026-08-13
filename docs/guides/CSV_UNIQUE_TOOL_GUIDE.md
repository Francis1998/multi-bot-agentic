# CSV Unique Tool User Guide

![CSV unique flow](../../assets/demo/csv-unique.gif)

## Why

Agents often need CSV rows unique on one or more named columns before the next
turn without asking a model to drop the wrong duplicate. **multi-bot-agentic**
includes `csv_unique` as a deterministic, allowlisted stdlib `csv` deduper that
is safe for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.

## Usage

Programmatic arguments:

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.csv_unique import CsvUniqueTool

result = CsvUniqueTool().execute(
    ToolInvocation(
        tool_name="csv_unique",
        arguments={
            "text": "name,score\nAda,2\nAda,9\nGrace,10\n",
            "columns": "name",
        },
    )
)
print(result.content)
```

Via the decision-engine directive (single payload + sentinel):

```text
TOOL:csv_unique:name,team,score
Ada,A,2
Ada,A,9
Grace,B,10
<<<CSV_UNIQUE>>>name,team
```

`columns` may be a comma-separated string or a list of names. The first row for
each key is kept; later duplicates are dropped.

## Behavior

The header row is preserved first. Data rows are keyed by the named column(s)
and later collisions are discarded. Empty input, oversized documents,
missing/duplicate headers, unknown columns, uneven rows, and row/column
overages return `ok=False`.

## Bounds

| Limit | Value |
|---|---|
| Max CSV chars | 20_000 |
| Max data rows | 500 |
| Max columns | 64 |
| Keep policy | first occurrence |
| Parser | Python stdlib `csv` only |
| Network access | none |

## Safety

Listed in `SafetyPolicy.allowed_tools` as `csv_unique`. It uses only stdlib
`csv`, with no network or code execution. See `docs/SAFETY.md`.
