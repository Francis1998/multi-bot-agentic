# CriticSelfConsistencyBandGuard Guide

![CriticSelfConsistencyBandGuard HITL flow](../../assets/demo/critic-self-consistency-band-guard.gif)

Offline HITL guard/advisor. Never auto-acts. Closes closed-UI gaps vs AutoGen/CrewAI/LangGraph critic self-consistency bands.

Optional later polish via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

Distinct from ``CriticAgreementEntropyGate`` and ``CriticPairwiseKappaGate``.

## Usage

```python
from multi_bot_agentic.critic_self_consistency import CriticSelfConsistencyBandGuard

status = CriticSelfConsistencyBandGuard().check("session-1", disagreement_rate=0.375)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Always `requires_human_review=True`. No HTTP. Humans decide. See `docs/SAFETY.md`.
