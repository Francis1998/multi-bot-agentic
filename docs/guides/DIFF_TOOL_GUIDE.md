# Diff Tool User Guide

![Unified diff flow](../demo.gif)

## Why

Popular agent frameworks (LangGraph toolkits, OpenAI Agents SDK examples, Claude
tool-use demos) ship a dedicated **diff/compare** helper so the model does not
hallucinate hunks. **multi-bot-agentic** now includes the same capability as a
deterministic, allowlisted tool — safe for GPT-5.5 / Claude Sonnet 4.6 /
Gemini 3.x / Kimi K2 workers.

## Usage

Programmatic (two arguments):

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.diff_text import DiffTool

result = DiffTool().execute(
    ToolInvocation(
        tool_name="diff",
        arguments={"text": "before\n", "other": "after\n"},
    )
)
print(result.content)
```

Via the decision-engine directive (single payload + sentinel):

```text
TOOL:diff:before
<<<DIFF>>>
after
```

## Bounds

| Limit | Value |
|---|---|
| Max chars per side | 20_000 |
| Max output lines | 2_000 |
| Context lines | 0–32 (default 3) |

Empty sides, oversized input, ambiguous sentinels, and invalid `context` return
`ok=False` structured failures — never exceptions into the run loop.

## Safety

Listed in `SafetyPolicy.allowed_tools` as `diff`. No network, no code execution,
stdlib `difflib` only. See `docs/SAFETY.md`.
