# Braille Tool Guide

![Braille demo](../../assets/demo/braille.gif)

Deterministic ASCII ↔ Unicode Braille codec for GPT-5.4 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.

## Why

Models invent arbitrary Braille mappings. This tool maps each ASCII byte onto the Unicode Braille Patterns block (U+2800+) and back with no network. Inspired by text utilities in popular agent/tool runtimes (CrewAI/LangChain community utilities).

## Usage

```python
from multi_bot_agentic.tools.braille import BrailleTool
from multi_bot_agentic.models import ToolInvocation

tool = BrailleTool()
encoded = tool.execute(ToolInvocation(tool_name="braille", arguments={"text": "Hi"}))
assert encoded.content == "⡈⡩"
```

## Bounds

- Max 2000 characters
- Modes: `encode` (default), `decode`
- Encode: ASCII only (U+0000..U+007F)
- Decode: Braille cells U+2800..U+287F

## Safety

Allowlisted; no network; pure local code-point mapping.
