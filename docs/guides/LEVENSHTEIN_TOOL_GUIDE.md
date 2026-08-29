# levenshtein Tool Guide

![levenshtein demo](../../assets/demo/levenshtein.gif)

Compute deterministic Levenshtein edit distance for fuzzy matching before the
next GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 turn.

## Why

CrewAI / LangGraph-style agents need a stable similarity signal for typos and
near-duplicate labels. Models invent distances; `levenshtein` uses classic
unit-cost DP with no network access (inspired by fuzzywuzzy / rapidfuzz agent
tooling, implemented with stdlib only).

## Usage

```python
tool.execute(
    ToolInvocation(
        tool_name="levenshtein",
        arguments={"a": "kitten", "b": "sitting"},
    )
)
```

## Bounds & Safety

- Required: `a`, `b` (max 2000 chars each)
- Content is the decimal distance string; metadata includes `distance`
- Never executes code or makes network requests
