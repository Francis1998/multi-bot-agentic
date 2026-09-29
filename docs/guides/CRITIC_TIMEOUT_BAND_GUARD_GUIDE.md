# CriticTimeoutBandGuard Guide

![CriticTimeoutBandGuard](../../assets/demo/critic-timeout-band-guard.gif)

Closes AutoGen / CrewAI / LangGraph critic-pass timeouts gaps.

Optional later polish via **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

Distinct from `CriticPassBudgetLimiter` and `ConsensusTimeoutBandGuard`.

## Usage

```python
from multi_bot_agentic.critic_timeout_band import CriticTimeoutBandGuard

status = CriticTimeoutBandGuard().check("session-1", waited_s=1.0, timeout_s=10.0)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Always `requires_human_review=True`. No HTTP. Humans decide.
