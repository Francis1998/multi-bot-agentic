# Use Case: PII redaction must catch parenthesized area-code phone numbers

**Issue:** #011
**Repository:** multi-bot-agentic

## Problem

The `redact` tool scrubs common PII (emails, phone numbers, SSNs, IPv4
addresses) before free-form text is persisted to the durable event log. Its
phone pattern was anchored with a leading word boundary:

```python
re.compile(r"\b(?:\+?\d{1,3}[.\s-]?)?(?:\(\d{3}\)|\d{3})[.\s-]?\d{3}[.\s-]?\d{4}\b")
```

The pattern includes a `\(\d{3}\)` branch to cover the extremely common US
format `(415) 555-1234`. But a leading `\b` can only match between a word and a
non-word character, and `(` is a non-word character. When such a number is
preceded by whitespace or appears at the start of the text (the normal case),
the position before `(` is *not* a word boundary, so the pattern never engaged
and the number leaked through unredacted:

```text
input:  "Reach me at (415) 555-1234 anytime"
output: "Reach me at (415) 555-1234 anytime"   # PII not redacted
```

This is a privacy defect: a number the tool was explicitly designed to catch was
written verbatim into the durable, replayable event log.

## How this agent solves it

The phone pattern now uses non-consuming `(?<!\w)` / `(?!\w)` boundaries instead
of `\b`. These hold whether the number starts with a digit *or* a `(`, so a
parenthesized area code preceded by whitespace is recognised, while numbers
embedded inside a longer word/digit run are still rejected:

```text
input:  "Reach me at (415) 555-1234 anytime"
output: "Reach me at [PHONE] anytime"
```

Hyphenated, dotted, spaced, and country-code-prefixed formats continue to be
redacted as before.

## Agentic design elements

| Component | Role |
|-----------|------|
| Safety controls | Redaction sanitises PII before it reaches durable storage |
| Event log | Only receives the placeholder, never the raw number |
| Tool adapter | Returns per-category counts so redaction is auditable |

## Try it

```bash
pytest tests/test_redaction_tool.py::test_redact_scrubs_parenthesized_area_code_phone -q
```
