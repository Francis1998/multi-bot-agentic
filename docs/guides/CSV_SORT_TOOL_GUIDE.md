# CSV Sort Tool User Guide

![CSV sort flow](../../assets/demo/csv-sort.gif)

## Why

Agents often need CSV rows ordered by a named column before the next turn
without asking a model to reshuffle quoted cells. **multi-bot-agentic** includes
`csv_sort` as a deterministic, allowlisted stdlib `csv` sorter that is safe for
GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.

## Usage

Programmatic arguments:

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.csv_sort import CsvSortTool

result = CsvSortTool().execute(
    ToolInvocation(
        tool_name="csv_sort",
        arguments={
            "text": "name,score\nGrace,10\nAda,2\n",
            "column": "score",
            "descending": False,
            "numeric": True,
        },
    )
)
print(result.content)
```

Via the decision-engine directive (single payload + sentinel):

```text
TOOL:csv_sort:name,score
Grace,10
Ada,2
<<<CSV_SORT>>>score
```

Optional `descending` and `numeric` flags default to `false` and are supplied
as separate arguments. When `numeric=true`, values parse as floats for ordering
and non-numeric cells sort after all numeric ones.

## Behavior

The header row is preserved first. Data rows sort by the named column
lexicographically (or numerically when requested). Empty input, oversized
documents, missing/duplicate headers, unknown columns, uneven rows, and
row/column overages return `ok=False`.

## Bounds

| Limit | Value |
|---|---|
| Max CSV chars | 20_000 |
| Max data rows | 500 |
| Max columns | 64 |
| Default descending | false |
| Default numeric | false |
| Parser | Python stdlib `csv` only |
| Network access | none |

## Safety

Listed in `SafetyPolicy.allowed_tools` as `csv_sort`. It uses only stdlib
`csv`, with no network or code execution. See `docs/SAFETY.md`.
