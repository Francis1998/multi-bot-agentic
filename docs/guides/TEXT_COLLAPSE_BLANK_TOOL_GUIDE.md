# text_collapse_blank Tool Guide

![text_collapse_blank demo](../../assets/demo/text-collapse-blank.gif)

Collapse consecutive blank or whitespace-only lines before the next GPT-5.5 /
Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 turn.

## Why

Long agent traces accumulate empty lines. Asking a model to tidy whitespace is
unreliable; this tool is deterministic and bounded.

## Usage

```python
tool.execute(
    ToolInvocation(
        tool_name="text_collapse_blank",
        arguments={"text": "line\n\n\n\nnext", "max_blank": 1},
    )
)
```

Sentinel form: `text<<<TEXT_COLLAPSE_BLANK>>>2`

## Bounds & Safety

- Max 20_000 input/output chars
- `max_blank` in 0..100 (default 1)
- Never executes code or makes network requests
