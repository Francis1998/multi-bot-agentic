# Regex Replace Tool User Guide

![Regex replace flow](../../assets/demo/regex-replace.gif)

## Why

Agents routinely need a deterministic find/replace before the next LLM turn.
Inventing replacements in-model drifts across turns and corrupts surrounding
text. **multi-bot-agentic** includes `regex_replace` as a bounded, allowlisted
substitution via stdlib `re` that is safe for GPT-5.5 / Claude Sonnet 4.6 /
Gemini 3.x / Kimi K2 workers.

## Usage

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.regex_replace import RegexReplaceTool

result = RegexReplaceTool().execute(
    ToolInvocation(
        tool_name="regex_replace",
        arguments={
            "text": "foo bar foo",
            "pattern": "foo",
            "repl": "baz",
            "count": 0,
        },
    )
)
print(result.content)
```

A model requests it with `TOOL:regex_replace:<text>` plus `pattern` / `repl`
(and optional `count`) arguments.

## Bounds

- Max document size: 20_000 characters
- Max pattern length: 200 characters
- Max replacement length: 2_000 characters
- Max matches / replacements: 100
- Nested quantifiers (e.g. `(a+)+`) and oversized group/alternation counts are
  rejected to reduce catastrophic backtracking risk
- `count` default 0 (replace all up to the match cap); must be >= 0

## Safety

- Stdlib `re` only — no code execution, no network
- Allowlisted in `SafetyPolicy.allowed_tools`
- Registered in `build_default_tools`

## Suggested repo metadata

- **Description:** Multi-bot agentic runtime with allowlisted tools, safety
  policy, and GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.
- **Topics:** `agentic-ai`, `multi-agent`, `llm-tools`, `python`, `safety`
