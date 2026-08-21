# CSV Stack Tool User Guide

![CSV stack flow](../../assets/demo/csv-stack.gif)

## Why

Agents routinely receive compatible CSV fragments from multiple workers and
need one table with a single header. Concatenating them in-model can duplicate
headers, reorder cells, or silently combine incompatible schemas.
**multi-bot-agentic** includes `csv_stack` as a deterministic, allowlisted
stdlib `csv` operation safe for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x /
Kimi K2 workers.

## Usage

Supply a list of CSV documents:

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.csv_stack import CsvStackTool

result = CsvStackTool().execute(
    ToolInvocation(
        tool_name="csv_stack",
        arguments={
            "csvs": [
                "model,score\nGPT-5.5,95\nClaude Sonnet 4.6,94\n",
                "model,score\nGemini 3.x,93\nKimi K2,92\n",
            ]
        },
    )
)
print(result.content)
```

Or use the sentinel in a decision-engine directive:

```text
TOOL:csv_stack:model,score
GPT-5.5,95
<<<CSV_STACK>>>model,score
Gemini 3.x,93
```

## Behavior

`csv_stack` accepts either `csvs` as a list of at least two strings or `text`
containing at least two documents separated by `<<<CSV_STACK>>>`. It validates
each document with stdlib `csv`, requires identical non-empty unique headers in
the same order, emits that header once, and appends non-blank data rows in input
order.

Mismatched headers, empty documents, malformed quoting, uneven rows, ambiguous
argument forms, and bound violations return `ok=False`.

## Bounds

| Limit | Value |
|---|---|
| Max total input / output chars | 20,000 |
| Minimum documents | 2 |
| Max output data rows | 500 |
| Max columns | 64 |
| Network access | none |

## Safety

Listed in `SafetyPolicy.allowed_tools` as `csv_stack`. It uses bounded stdlib
CSV parsing and serialization only, with no network, file access, or code
execution. See `docs/SAFETY.md`.
