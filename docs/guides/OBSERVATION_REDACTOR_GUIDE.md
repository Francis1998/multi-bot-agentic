# Observation Redactor Guide

![Observation redactor demo](../../assets/demo/observation-redactor.gif)

Scrub emails, phones, SSN-like values, and `sk-` / `Bearer` tokens from
observation text before it hits the durable event log.

Works with **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro** agent loops.

## Gap vs AutoGen / CrewAI

| Capability | multi-bot-agentic | AutoGen / CrewAI |
| --- | --- | --- |
| Focus | Observation/log redaction | Often raw event transcripts |
| Patterns | email / phone / ssn / token | Framework-dependent |
| Wiring | Caller-driven `redact(text)` | Often post-hoc filtering |

## Usage

```python
from multi_bot_agentic.observation_redactor import ObservationRedactor

result = ObservationRedactor().redact("ping ada@example.com with Bearer abc.sk-abcdefghijklmnopqrst")
assert "[EMAIL]" in result.redacted_text
assert result.redaction_count >= 1
print(result.categories)
```
