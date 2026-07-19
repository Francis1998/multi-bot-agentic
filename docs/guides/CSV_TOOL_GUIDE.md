# CSV Parse Tool User Guide

![CSV parse flow](../../assets/demo/csv-parse.gif)

## Why

Popular agent frameworks (LangGraph toolkits, OpenAI Agents SDK examples, Claude
tool-use demos) ship a dedicated **CSV/table** helper so the model does not
invent columns. **multi-bot-agentic** now includes the same capability as a
deterministic, allowlisted tool — safe for GPT-5.5 / Claude Sonnet 4.6 /
Gemini 2.5 / Kimi K2 workers.

## Usage

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.csv_parse import CsvParseTool

result = CsvParseTool().execute(
    ToolInvocation(
        tool_name="csv",
        arguments={"text": "name,age\nAda,36\nGrace,45\n"},
    )
)
print(result.content)
```

Via the decision-engine directive:

```text
TOOL:csv:name,age
Ada,36
Grace,45
```

## Bounds

| Limit | Value |
|---|---|
| Max document chars | 20_000 |
| Max data rows | 200 |
| Max columns | 32 |
| Default delimiter | `,` |

Empty input, oversized tables, and invalid delimiters return `ok=False`
structured failures — never exceptions into the run loop.

## Redaction IPv6 note

The companion `redact` tool now scrubs IPv6 literals such as `2001:db8::1` and
`::1` to `[IP]`, matching the existing IPv4 behaviour.

## Safety

Listed in `SafetyPolicy.allowed_tools` as `csv`. No network, no code execution,
stdlib `csv` only. See `docs/SAFETY.md`.
