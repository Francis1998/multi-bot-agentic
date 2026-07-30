# CSV TSV Bridge Tool User Guide

![CSV TSV bridge flow](../../assets/demo/csv-tsv.gif)

## Why

Agents often need to move tabular snippets between CSV (spreadsheet exports,
API payloads) and TSV (prompt-friendly tab tables, shell paste). Converting by
hand is error-prone across providers. **multi-bot-agentic** includes `csv_tsv`
as a deterministic, allowlisted bridge that is safe for GPT-5.5 / Claude Sonnet
4.6 / Gemini 3.x / Kimi K2 workers.

## Usage

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.csv_tsv import CsvTsvTool

result = CsvTsvTool().execute(
    ToolInvocation(
        tool_name="csv_tsv",
        arguments={
            "text": """model,score
GPT-5.5,95
Claude Sonnet 4.6,92
""",
            "direction": "csv_to_tsv",
        },
    )
)
print(result.content)
```

Convert TSV back to CSV:

```python
result = CsvTsvTool().execute(
    ToolInvocation(
        tool_name="csv_tsv",
        arguments={
            "text": "model\tscore\nGemini 3.x\t90\nKimi K2\t88\n",
            "direction": "tsv_to_csv",
        },
    )
)
```

Optional single-character `delimiter` overrides the *input* field separator
(default `,` for `csv_to_tsv`, tab for `tsv_to_csv`).

Via the decision-engine directive:

```text
TOOL:csv_tsv:model,score
GPT-5.5,95
Kimi K2,88
```

Use `direction` in structured invocations when converting TSV to CSV.

## Behavior

Parsing and serialization use the stdlib `csv` module only. The tool:

- defaults `direction` to `csv_to_tsv` when omitted;
- treats the first row as the header that defines column width;
- rejects rows whose column count differs from the header;
- strips trailing blank rows;
- re-serializes with `\n` line endings and no trailing blank line;
- quotes fields that need escaping when emitting CSV.

Empty documents, oversized input, invalid direction/delimiter, malformed
CSV/TSV, and ragged tables return `ok=False` structured failures instead of
being evaluated.

## Bounds

| Limit | Value |
|---|---|
| Max document chars | 20_000 |
| Directions | `csv_to_tsv`, `tsv_to_csv` |
| Default input delimiter | `,` (`csv_to_tsv`) or tab (`tsv_to_csv`) |
| Output delimiter | tab (`csv_to_tsv`) or `,` (`tsv_to_csv`) |
| Column width | Defined by header row |
| Parse runtime | stdlib `csv` only |

## Safety

Listed in `SafetyPolicy.allowed_tools` as `csv_tsv`. No network, no code
execution, and no constructor hooks. See `docs/SAFETY.md`.
