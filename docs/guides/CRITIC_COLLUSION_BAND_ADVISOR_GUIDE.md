# CriticCollusionBandAdvisor Guide

![CriticCollusionBandAdvisor](../../assets/demo/critic-collusion-band-advisor.gif)

Offline HITL advisor. Never network I/O.
Gap vs AutoGen/CrewAI/LangGraph critic-collusion band advisors. Distinct from `CriticAgreementEntropyAdvisor` / `CriticVerdictDiversityAdvisor`.

Optional polish via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Usage

```python
from multi_bot_agentic.critic_collusion_band import CriticCollusionBandAdvisor

status = CriticCollusionBandAdvisor().check("s1", collusion_score=0.35)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Always HITL. Humans decide.
