# CriticDisagreementSpreadAdvisor Guide

![CriticDisagreementSpreadAdvisor](../../assets/demo/critic-disagreement-spread.gif)

Offline HITL advisor for `disagreement_ratio` bands. Gap vs AutoGen/CrewAI/LangGraph critic disagreement-spread monitors. Distinct from `CriticAgreementEntropyGate` / `CriticPairwiseKappaGate`.

Optional polish via **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

## Usage

```python
from multi_bot_agentic.critic_disagreement_spread import CriticDisagreementSpreadAdvisor

status = CriticDisagreementSpreadAdvisor().advise("s1", disagreement_ratio=0.3)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Advisory only. No network I/O. Humans decide.
