# csv_transpose Tool Guide

![csv_transpose demo](../../assets/demo/csv-transpose.gif)

Transpose CSV tables before GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2
turns. Inspired by spreadsheet transpose helpers in popular agent toolkits.

## Usage

```python
tool.execute(ToolInvocation(tool_name="csv_transpose", arguments={"text": "a,b\n1,2\n"}))
```

## Bounds & Safety

- Max 20_000 chars, 500 rows, 64 columns
- Short rows are padded; malformed CSV is rejected
- Never executes code or makes network requests
