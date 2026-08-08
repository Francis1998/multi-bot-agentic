# UUID4 Tool User Guide

![UUID4 flow](../../assets/demo/uuid4.gif)

## Why

Agents often need a fresh opaque identifier for a correlation id, temporary
handle, or client-side token. Deterministic ``uuid5`` is the right choice when
the same inputs must always yield the same id. When uniqueness without
reproducibility is enough, **multi-bot-agentic** includes ``uuid4`` as an
allowlisted generator that is safe for GPT-5.5 / Claude Sonnet 4.6 /
Gemini 3.x / Kimi K2 workers.

## Usage

```python
from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.uuid4 import Uuid4Tool

result = Uuid4Tool().execute(ToolInvocation(tool_name="uuid4", arguments={"count": 1}))
print(result.content)
```

A model requests it with `TOOL:uuid4:` (optional payload unused) or programmatically
with `count`.

Generate several at once:

```python
result = Uuid4Tool().execute(ToolInvocation(tool_name="uuid4", arguments={"count": 3}))
print(result.content)  # three newline-joined UUID strings
```

## Bounds

| Limit | Value |
|---|---|
| `count` | integer 1..16 (default 1) |
| Output | one UUID string, or newline-joined when `count` > 1 |

Out-of-range or non-integer `count` returns `ok=False` structured failures —
never exceptions into the run loop.

## Non-crypto note

UUIDv4 values are **random opaque identifiers**, not cryptographic secrets.
Do not use them as API keys, password material, signing keys, or CSRF tokens.
CPython draws entropy via `os.urandom`, but the UUID format and this tool's
contract are about collision-resistant ids for agent workflows — not
authenticated security primitives. Prefer dedicated secret generators and
key-management systems for anything that must stay confidential.

Unlike ``uuid5``, output is intentionally non-deterministic across calls.

## Safety

Listed in `SafetyPolicy.allowed_tools` as `uuid4`. No network, no code
execution — stdlib `uuid.uuid4` only. See `docs/SAFETY.md`.
