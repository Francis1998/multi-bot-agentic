# Use Case: OpenAI-compatible gateways may return structured content

**Issue:** #007
**Repository:** multi-bot-agentic

## Problem

The base OpenAI Chat Completions contract returns the assistant reply as
`choices[0].message.content` — a plain string. Several widely used
OpenAI-compatible gateways (LiteLLM, vLLM, OpenRouter, and some provider shims)
instead return `content` as a list of typed parts, for example:

```json
{"choices": [{"message": {"content": [
  {"type": "text", "text": "DONE:"},
  {"type": "text", "text": " ok"}
]}}]}
```

`_extract_openai_text` only accepted a string and raised `ValueError` for the
list shape. Because the runner treats `ValueError` as a provider failure, a
perfectly valid reply from a compatible gateway was recorded as `RUN_FAILED`.
Since `KimiAdapter` subclasses `OpenAIAdapter`, the same gap affected Kimi.

## How this agent solves it

`_extract_openai_text` now returns a string reply directly and, when the reply
is a list, joins the string and `{"text": ...}` parts into the assistant text.
Unknown shapes still raise `ValueError` so genuine protocol breakage surfaces as
a normal provider failure. This mirrors how the Gemini adapter already joins
`parts[*].text`.

## Agentic design elements

| Component | Role |
|-----------|------|
| LLM adapters | Normalize provider-specific response shapes into one `ModelOutput` text |
| Runner loop | Consumes normalized text; only truly malformed replies fail the run |
| Event log | Records the synthesized answer instead of a spurious failure |

## Try it

```bash
pytest tests/test_adapters.py::test_openai_parser_consumes_structured_content_parts -q
```
