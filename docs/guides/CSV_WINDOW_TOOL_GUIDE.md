# CSV Window Tool User Guide

![CSV window flow](../../assets/demo/csv-window.gif)

## Why

Agents often need consecutive row slices from a table without copying headers or
manually chopping rows in a model turn. **multi-bot-agentic** includes
`csv_window` as a deterministic, allowlisted stdlib `csv` sliding-window
operation safe for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.

## Usage

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.csv_window import CsvWindowTool

result = CsvWindowTool().execute(
    ToolInvocation(
        tool_name="csv_window",
        arguments={
            "text": ("model,score\nGPT-5.5,95\nClaude Sonnet 4.6,94\nGemini 3.x,93\nKimi K2,92\n"),
            "window_size": 2,
            "step": 1,
            "start_row": 0,
        },
    )
)
print(result.content)
```

Via the decision-engine directive (programmatic options still required for
window sizing):

```text
TOOL:csv_window:model,score
GPT-5.5,95
Claude Sonnet 4.6,94
```

## Behavior

`csv_window` parses one CSV document, keeps the header once per window, and
emits sliding windows of exactly `window_size` data rows. Windows are joined by
a blank line. Optional `step` (default 1) controls the stride, `start_row`
(default 0) skips leading data rows, and `index` returns a single 0-based
window when set.

Missing/invalid options, malformed CSV, empty documents, windows that cannot
fit, out-of-range index/start, and bound violations return `ok=False`.

## Bounds

| Limit | Value |
|---|---|
| Max total input / output chars | 20,000 |
| Max data rows | 500 |
| Max columns | 64 |
| Default step / start_row | 1 / 0 |
| Network access | none |

## Safety

Listed in `SafetyPolicy.allowed_tools` as `csv_window`. It uses bounded stdlib
CSV parsing and serialization only, with no network, file access, or code
execution. See `docs/SAFETY.md`.
