# NATO Phonetic Tool Guide

![NATO Phonetic demo](../../assets/demo/nato-phonetic.gif)

Deterministic NATO phonetic alphabet for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.

## Why

Models hallucinate phonetic words. This tool converts text to/from the standard NATO phonetic alphabet with no network.

## Usage

```python
from multi_bot_agentic.tools.nato_phonetic import NatoPhoneticTool
from multi_bot_agentic.models import ToolInvocation

tool = NatoPhoneticTool()
result = tool.execute(ToolInvocation(tool_name="nato_phonetic", arguments={"text": "SOS"}))
assert result.content == "Sierra Oscar Sierra"
```

## Bounds

- Max 2000 characters
- Modes: `encode` (default), `decode`
- Non-alpha/digit characters pass through in encode mode
- Decode splits on whitespace; unknown words pass through

## Safety

Allowlisted; no network; no file access.
