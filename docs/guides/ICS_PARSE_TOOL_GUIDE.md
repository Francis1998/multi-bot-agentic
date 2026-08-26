# ics_parse Tool Guide

![ics_parse demo](../../assets/demo/ics-parse.gif)

Parse iCalendar (`.ics`) VEVENT fields before the next GPT-5.5 /
Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 turn.

## Why

Calendar exports and invite snippets are common in agent frameworks, but this
repo had no ICS parser. Models routinely mis-read folded lines or invent
`DTSTART` values. `ics_parse` is a deterministic stdlib-only extractor.

## Usage

```python
tool.execute(
    ToolInvocation(
        tool_name="ics_parse",
        arguments={"text": "BEGIN:VEVENT\nSUMMARY:Sync\nDTSTART:20260826T160000Z\nEND:VEVENT\n"},
    )
)
```

Output is JSON Lines (one event object per line) with
`SUMMARY` / `DTSTART` / `DTEND` / `UID` / `LOCATION`.

## Bounds & Safety

- Max 20_000 input/output chars
- Max 100 VEVENT blocks
- No `icalendar` dependency; never executes code or makes network requests
