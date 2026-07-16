# ISSUE-014: Slugify must not eat edge letters with alphanumeric separators

![Demo](../demo.gif)

## Problem

`SlugifyTool` finished with `collapsed.strip(separator)`. Python's
`str.strip(chars)` treats `chars` as a **character set**, not an exact suffix.
The separator pattern allows alphanumeric separators (`[A-Za-z0-9_-]{1,8}`), so:

| Input | Previous | Expected |
|---|---|---|
| `text="test"`, `separator="t"` | `"es"` | `"test"` |
| `text="apple"`, `separator="a"` | `"pple"` | `"apple"` |

Agents using GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 that asked for a
custom separator (branch tokens, cache keys) silently corrupted the slug.

## Fix

Trim **whole-separator** prefixes/suffixes only (`_trim_separator`), never
character-set strip.

## Verify

```bash
PATH="$PWD/.venv/bin:$PATH" VIRTUAL_ENV="" bash scripts/check.sh
```
