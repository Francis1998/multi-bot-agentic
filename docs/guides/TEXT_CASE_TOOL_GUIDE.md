# Text Case Tool User Guide

![Text case flow](../../assets/demo/text-case.gif)

## Why

Agents routinely need a stable case transform — lower, upper, title, snake,
kebab, or camel — before using free-form text as a key or label. Rewriting
case in-model is unreliable. **multi-bot-agentic** includes `text_case` as a
deterministic, allowlisted converter that is safe for GPT-5.5 /
Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.

## Usage

Programmatic arguments:

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.text_case import TextCaseTool

result = TextCaseTool().execute(
    ToolInvocation(
        tool_name="text_case",
        arguments={"text": "Hello World!", "case": "snake"},
    )
)
print(result.content)  # hello_world
```

Via the decision-engine directive (single payload + sentinel):

```text
TOOL:text_case:Hello World!<<<TEXT_CASE>>>kebab
```

When `case` is omitted (and no sentinel is present), the default is `lower`.

## Behavior

| `case` | Result for `Hello World!` |
|---|---|
| `lower` | `hello world!` |
| `upper` | `HELLO WORLD!` |
| `title` | `Hello World!` |
| `snake` | `hello_world` |
| `kebab` | `hello-world` |
| `camel` | `helloWorld` |

Snake/kebab/camel split on non-alphanumeric runs and camelCase boundaries.
Empty, oversized, and unsupported `case` values return `ok=False`.

## Bounds

| Limit | Value |
|---|---|
| Max text chars | 20_000 |
| Supported cases | lower, upper, title, snake, kebab, camel |
| Network access | none |

## Safety

Listed in `SafetyPolicy.allowed_tools` as `text_case`. No network, no code
execution. See `docs/SAFETY.md`.
