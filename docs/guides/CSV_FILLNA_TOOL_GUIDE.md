# CSV Fillna Tool User Guide

![CSV fillna flow](../../assets/demo/csv-fillna.gif)

## Why

Sparse CSV handoffs often need a constant fill (pandas-style `fillna`) before
the next GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 turn. Asking a
model to rewrite blank cells can scramble quoted fields. **multi-bot-agentic**
includes `csv_fillna` as a deterministic, allowlisted stdlib `csv` filler.

## Usage

Programmatic arguments:

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.csv_fillna import CsvFillnaTool

result = CsvFillnaTool().execute(
    ToolInvocation(
        tool_name="csv_fillna",
        arguments={
            "text": "model,score\nGPT-5.5,\n,2\n",
            "fill_value": "NA",
            "columns": "score",
        },
    )
)
print(result.content)
```

Via the decision-engine directive (single payload + sentinel):

```text
TOOL:csv_fillna:model,region,score
GPT-5.5,,1
,eu,
<<<CSV_FILLNA>>>NA<<<COLUMNS>>>model,score
```

`fill_value` defaults to an empty string. Omitting `columns` fills every
column; providing `columns` limits the fill to that subset.

## Behavior

The header row is preserved. Data cells whose stripped value is empty become
`fill_value`. Empty input, oversized documents, missing/duplicate headers,
unknown columns, and row/column overages return `ok=False`.

## Bounds

| Limit | Value |
|---|---|
| Max CSV chars | 20_000 |
| Max data rows | 500 |
| Max columns | 64 |
| Default fill_value | `""` |
| Parser | Python stdlib `csv` only |
| Network access | none |

## Safety

Listed in `SafetyPolicy.allowed_tools` as `csv_fillna`. It uses only stdlib
`csv`, with no network or code execution. See `docs/SAFETY.md`.
