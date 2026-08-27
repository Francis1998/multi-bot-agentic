# cron_next Tool Guide

![cron_next demo](../../assets/demo/cron-next.gif)

Preview the next UTC fire times for a classic 5-field cron expression before
the next GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 turn.

## Why

Scheduling agents (crontab.guru-style previews, APScheduler-like planners)
need deterministic expansion of minute/hour/dom/month/dow fields. Models
mis-handle day-of-week numbering and DOM/DOW OR semantics. `cron_next`
evaluates a small stdlib-only cron subset (no `croniter`).

## Usage

```python
tool.execute(
    ToolInvocation(
        tool_name="cron_next",
        arguments={
            "expression": "0 9 * * 1",
            "count": 2,
            "from_iso": "2026-08-27T00:00:00Z",
        },
    )
)
```

`text` is accepted as an alias for `expression`. Content is one ISO-8601 UTC
timestamp per line (`YYYY-MM-DDTHH:MM:SSZ`).

## Bounds & Safety

- Expression max 128 chars; exactly 5 fields
- Supports `*`, lists, ranges, and steps (`*/15`, `1-10/2`)
- `count` default 5, max 20; optional `from_iso` (UTC; defaults to current UTC minute)
- Never executes code or makes network requests
