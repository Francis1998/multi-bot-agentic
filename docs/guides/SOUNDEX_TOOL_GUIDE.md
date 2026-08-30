# soundex Tool Guide

![soundex demo](../../assets/demo/soundex.gif)

Compute deterministic American Soundex phonetic codes for fuzzy name matching
before the next GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 turn.

## Why

CrewAI / LangChain-style agents need a stable phonetic fingerprint when
reconciling person names or vendor labels. Models invent codes; `soundex` uses
classic American Soundex with no network access (inspired by fuzzy name-matching
agent toolkits, implemented with stdlib only).

## Usage

```python
tool.execute(
    ToolInvocation(
        tool_name="soundex",
        arguments={"text": "Robert"},
    )
)
```

## Bounds & Safety

- Required: `text` (max 2000 chars)
- Content is the 4-character Soundex code; metadata includes `soundex`
- Never executes code or makes network requests
