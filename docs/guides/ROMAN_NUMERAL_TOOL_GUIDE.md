# Roman Numeral Tool Guide

![Roman numeral demo](../../assets/demo/roman-numeral.gif)

Deterministic Roman encode/decode for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.

## Why

Models invent subtractive pairs. This tool encodes 1..3999 and decodes canonical Roman strings with no network. Common in agent toolkits that expose text transforms alongside calculators.

## Usage

```python
from multi_bot_agentic.tools.roman_numeral import RomanNumeralTool
from multi_bot_agentic.models import ToolInvocation

tool = RomanNumeralTool()
result = tool.execute(ToolInvocation(tool_name="roman_numeral", arguments={"text": "1994"}))
assert result.content == "MCMXCIV"
```

## Bounds

- Max 2000 characters
- Encode range: 1..3999
- Modes: `encode` (default), `decode` (canonical forms only)

## Safety

Allowlisted; no network; pure string/integer transform.
