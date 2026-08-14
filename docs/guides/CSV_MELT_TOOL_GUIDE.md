# CSV Melt Tool User Guide

![CSV melt flow](../../assets/demo/csv-melt.gif)

## Why

Agents often need wide CSV observations converted to long form without losing
identifier columns or mismatching column names and values. **multi-bot-agentic**
includes `csv_melt` as a deterministic, allowlisted stdlib `csv` reshape that
is safe for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.

Unlike the multi-mode `csv_pivot` tool, `csv_melt` has one focused operation
and always produces columns named `variable` and `value`.

## Usage

Programmatic arguments:

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.csv_melt import CsvMeltTool

result = CsvMeltTool().execute(
    ToolInvocation(
        tool_name="csv_melt",
        arguments={
            "text": "model,latency,cost\nGPT-5.5,120,4\n",
            "id_vars": "model",
            "value_vars": "latency,cost",
        },
    )
)
print(result.content)
```

Via the decision-engine directive (all non-ID columns are melted):

```text
TOOL:csv_melt:model,latency,cost
GPT-5.5,120,4
Claude Sonnet 4.6,150,3
<<<CSV_MELT>>>model
```

`id_vars` and `value_vars` may be comma-separated strings or lists. When
`value_vars` is omitted, every non-ID column is melted in header order. The
sentinel suffix supplies `id_vars` and uses that default.

## Behavior

Each nonblank input row produces one output row per selected value column. ID
values are repeated, the source header becomes `variable`, and the cell becomes
`value`. Empty input, duplicate or unnamed headers, unknown/overlapping
selections, uneven rows, oversized tables, and output expansion beyond the
bounds return `ok=False`.

## Bounds

| Limit | Value |
|---|---|
| Max input/output chars | 20_000 |
| Max input/output data rows | 500 |
| Max input columns | 64 |
| Output columns | `id_vars` + `variable`, `value` |
| Parser | Python stdlib `csv` only |
| Network access | none |

## Safety

Listed in `SafetyPolicy.allowed_tools` as `csv_melt`. It uses only stdlib `csv`,
with no network or code execution. See `docs/SAFETY.md`.
