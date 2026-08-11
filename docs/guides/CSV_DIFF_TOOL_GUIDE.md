# CSV Diff Tool User Guide

![CSV diff flow](../../assets/demo/csv-diff.gif)

## Why

Agents often need to identify record-level changes between two CSV exports
without copying whole changed rows into the next turn. **multi-bot-agentic**
includes `csv_diff` as a deterministic, allowlisted stdlib `csv` comparator
that is safe for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.

## Usage

Programmatic arguments:

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.csv_diff import CsvDiffTool

result = CsvDiffTool().execute(
    ToolInvocation(
        tool_name="csv_diff",
        arguments={
            "left": "id,status\n1,open\n2,open\n",
            "right": "id,status\n2,closed\n3,open\n",
            "key": "id",
        },
    )
)
print(result.content)
```

`key` may be a comma-separated string or a list/tuple for composite keys.

Via the decision-engine directive (single payload + sentinels):

```text
TOOL:csv_diff:id,status
1,open
2,open
<<<CSV_DIFF>>>
id,status
2,closed
3,open
<<<CSV_DIFF_KEY>>>id
```

The key may alternatively follow a second `<<<CSV_DIFF>>>` sentinel.

## Behavior

The result is canonical JSON containing:

- `added`: key maps present only in the right CSV
- `removed`: key maps present only in the left CSV
- `changed`: key maps present in both CSVs whose named-column values differ

Rows are compared by column name, so header reordering alone is not a change.
Results are sorted by key. Empty or duplicate primary-key values, missing key
columns, duplicate/blank headers, uneven rows, and malformed CSV return
`ok=False`.

## Bounds

| Limit | Value |
|---|---|
| Max combined CSV chars | 20_000 |
| Max data rows per CSV | 500 |
| Max columns per CSV | 64 |
| Parser | Python stdlib `csv` only |
| Network access | none |

## Safety

Listed in `SafetyPolicy.allowed_tools` as `csv_diff`. It uses only stdlib
`csv` and `json`, returns key maps rather than full row payloads, and performs
no network access or code execution. See `docs/SAFETY.md`.
