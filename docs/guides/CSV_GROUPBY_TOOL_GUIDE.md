# CSV Group-By Tool User Guide

![CSV group-by flow](../../assets/demo/csv-groupby.gif)

## Why

Agents routinely need to aggregate CSV snippets (sum/count/min/max/mean) by a
key column before the next LLM turn. Aggregating in-model invents totals and
drops groups. **multi-bot-agentic** includes `csv_groupby` as a deterministic,
allowlisted aggregation via stdlib `csv` that is safe for GPT-5.5 /
Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.

## Usage

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.csv_groupby import CsvGroupbyTool

result = CsvGroupbyTool().execute(
    ToolInvocation(
        tool_name="csv_groupby",
        arguments={
            "text": "team,value\na,1\na,3\nb,2\n",
            "by": "team",
            "values": "value",
            "agg": "sum",
        },
    )
)
print(result.content)
```

A model requests it with `TOOL:csv_groupby:<csv>` plus `by` / `values` / `agg`
arguments.

## Bounds

- Max document size: 20_000 characters
- Max rows: 500 (excluding header)
- Max columns: 64
- Aggregations: `sum` (default), `count`, `min`, `max`, `mean`
- Value columns must be numeric; empty or non-numeric cells fail closed

## Safety

- Stdlib `csv` / `statistics` only — no code execution, no network
- Allowlisted in `SafetyPolicy.allowed_tools`
- Registered in `build_default_tools`

## Suggested repo metadata

- **Description:** Multi-bot agentic runtime with allowlisted tools, safety
  policy, and GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.
- **Topics:** `agentic-ai`, `multi-agent`, `llm-tools`, `python`, `safety`
