# csv_to_json Tool Guide

![csv_to_json demo](../../assets/demo/csv-to-json.gif)

Parse CSV text into a JSON array of objects before the next GPT-5.5 /
Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 turn.

## Why

Agent pipelines need stable header-keyed records from small CSV exports.
Models invent keys and shift columns; `csv_to_json` uses stdlib `csv` with a
required header row and hard caps on size, rows, and columns. No network
access.

## Usage

```python
tool.execute(
    ToolInvocation(
        tool_name="csv_to_json",
        arguments={"csv": "name,role\nAda,engineer\n"},
    )
)
```

Optional `delimiter` overrides `,`. The `text` argument is accepted as an
alias for `csv`.

## Bounds & Safety

- Required: `csv` (max 20_000 chars); non-blank unique header row
- Caps: 500 body rows, 64 columns
- Content is pretty JSON (array of objects); metadata includes `rows`,
  `columns`, `header`
- Never executes code or makes network requests
