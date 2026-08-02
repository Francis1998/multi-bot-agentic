# CSV Pivot Tool User Guide

![CSV pivot flow](../../assets/demo/csv-pivot.gif)

## Why

Agents routinely need to reshape long CSV snippets into wide pivots (or back)
before the next LLM turn. Pivoting in-model invents columns and drops rows.
**multi-bot-agentic** includes `csv_pivot` as a deterministic, allowlisted
reshape via stdlib `csv` that is safe for GPT-5.5 / Claude Sonnet 4.6 /
Gemini 3.x / Kimi K2 workers.

## Usage

Programmatic pivot:

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.csv_pivot import CsvPivotTool

result = CsvPivotTool().execute(
    ToolInvocation(
        tool_name="csv_pivot",
        arguments={
            "text": "id,metric,value\na,x,1\na,y,2\n",
            "mode": "pivot",
            "index": "id",
            "columns": "metric",
            "values": "value",
        },
    )
)
print(result.content)
```

Unpivot wide columns:

```python
result = CsvPivotTool().execute(
    ToolInvocation(
        tool_name="csv_pivot",
        arguments={
            "text": "id,x,y\na,1,2\n",
            "mode": "unpivot",
            "id_vars": "id",
            "value_vars": "x,y",
        },
    )
)
```

Via the decision-engine directive:

```text
TOOL:csv_pivot:id,metric,value
a,x,1
a,y,2
```

## Behavior

Modes:

- `pivot` (default): requires `index`, `columns`, and `values` column names;
- `unpivot`: requires `id_vars` (comma-separated); optional `value_vars`,
  `var_name` (default `variable`), and `value_name` (default `value`).

Duplicate pivot cells, unknown columns, oversized tables, and malformed CSV
return `ok=False` structured failures.

## Bounds

| Limit | Value |
|---|---|
| Max text chars | 20_000 |
| Max rows | 500 |
| Max columns | 64 |
| Network access | none |

## Safety

Listed in `SafetyPolicy.allowed_tools` as `csv_pivot`. No network, no code
execution. See `docs/SAFETY.md`.
