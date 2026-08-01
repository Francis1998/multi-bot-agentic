# Unicode Normalize Tool User Guide

![Unicode normalize flow](../../assets/demo/unicode-normalize.gif)

## Why

Agents often receive text with mixed Unicode compatibility forms — pasted API
responses, filenames, or user input that combines composed and decomposed code
points. Normalizing in-model is unreliable. **multi-bot-agentic** includes
`unicode_normalize` as a deterministic, allowlisted normalizer that is safe
for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.

## Usage

Programmatic:

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.unicode_normalize import UnicodeNormalizeTool

result = UnicodeNormalizeTool().execute(
    ToolInvocation(
        tool_name="unicode_normalize",
        arguments={"text": "caf\u00e9", "form": "NFC"},
    )
)
print(result.content, result.metadata["form"])
```

Via the decision-engine directive:

```text
TOOL:unicode_normalize:café
```

## Behavior

Supported forms: `NFC` (default), `NFD`, `NFKC`, `NFKD`.

The tool returns normalized text in `content` and repeats the applied form in
metadata along with input and output character counts.

Empty, oversized, or unsupported-form input returns `ok=False` structured
failures.

## Bounds

| Limit | Value |
|---|---|
| Max text chars | 20_000 |
| Network access | none |

## Safety

Listed in `SafetyPolicy.allowed_tools` as `unicode_normalize`. No network, no
code execution. See `docs/SAFETY.md`.
