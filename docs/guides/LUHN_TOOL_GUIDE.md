# Luhn Tool Guide

![Luhn demo](../../assets/demo/luhn.gif)

Deterministic Luhn (mod-10) for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.

## Why

Models invent parity rules. This tool validates or completes digit strings with no network.

## Usage

```python
from multi_bot_agentic.tools.luhn import LuhnTool
from multi_bot_agentic.models import ToolInvocation

tool = LuhnTool()
result = tool.execute(ToolInvocation(tool_name="luhn", arguments={"text": "4111111111111111"}))
assert result.content == "true"
```

## Bounds

- Max 2000 characters
- Digits, spaces, and dashes only
- Modes: `validate` (default), `check_digit`

## Safety

Allowlisted; no network; does not store or transmit card data.
