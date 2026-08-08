# CSV Join Tool User Guide

![CSV join flow](../../assets/demo/csv-join.gif)

## Why

Agents routinely need to join two small CSV tables on a key column before the
next LLM turn. Joining in-model drops rows and duplicates keys.
**multi-bot-agentic** includes `csv_join` as a deterministic, allowlisted
inner/left join via stdlib `csv` that is safe for GPT-5.5 /
Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.

## Usage

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.csv_join import CsvJoinTool

result = CsvJoinTool().execute(
    ToolInvocation(
        tool_name="csv_join",
        arguments={
            "left": "id,name\n1,alice\n2,bob\n",
            "right": "id,score\n1,10\n2,20\n",
            "on": "id",
            "how": "inner",
        },
    )
)
print(result.content)
```

A model requests it with `TOOL:csv_join:<csv>` plus `right` and `on` (or
`left_on`/`right_on`) arguments. `text` may be used in place of `left`.

## Bounds

- Max combined document size: 20_000 characters
- Max rows per side: 500 (excluding header)
- Max columns per side: 64
- Join types: `inner` (default), `left`
- Provide either `on`, or both `left_on` and `right_on`

## Safety

- Stdlib `csv` only — no code execution, no network
- Allowlisted in `SafetyPolicy.allowed_tools`
- Registered in `build_default_tools`

## Suggested repo metadata

- **Description:** Multi-bot agentic runtime with allowlisted tools, safety
  policy, and GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.
- **Topics:** `agentic-ai`, `multi-agent`, `llm-tools`, `python`, `safety`
