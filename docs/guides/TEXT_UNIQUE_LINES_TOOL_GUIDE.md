# text_unique_lines Tool Guide

![text_unique_lines demo](../../assets/demo/text-unique-lines.gif)

Deduplicate noisy lines in first-seen order before the next GPT-5.5 /
Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 turn.

## Why

Agent traces and scraped candidate lists often repeat lines. Unlike
`text_sort_lines` with `unique=true`, this tool preserves original order —
matching the dedupe helpers popular agent frameworks expose for logs.

## Usage

```python
tool.execute(
    ToolInvocation(
        tool_name="text_unique_lines",
        arguments={"text": "a\nb\na\nc", "strip": True},
    )
)
```

Sentinel form: `text<<<TEXT_UNIQUE_LINES>>>false`

## Bounds & Safety

- Max 20_000 input/output chars
- `strip` default true (compare after strip)
- Never executes code or makes network requests
