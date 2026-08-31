# metaphone Tool Guide

![metaphone demo](../../assets/demo/metaphone.gif)

Compute deterministic classic Metaphone phonetic codes for fuzzy name matching
before the next GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 turn.

## Why

CrewAI / LangChain-style agents need a stable phonetic fingerprint when
reconciling person names or vendor labels. Models invent codes; `metaphone`
uses classic Metaphone (Lawrence Philips) — not Double Metaphone — with no
network access (inspired by fuzzy name-matching agent toolkits, implemented
with stdlib only).

## Usage

```python
tool.execute(
    ToolInvocation(
        tool_name="metaphone",
        arguments={"text": "Joseph"},
    )
)
```

## Bounds & Safety

- Required: `text` (max 2000 chars)
- Content is the classic Metaphone code; metadata includes `metaphone` and
  `algorithm: classic`
- Never executes code or makes network requests
