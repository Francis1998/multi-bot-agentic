# ConsensusVoteStuffingBandAdvisor Guide

![ConsensusVoteStuffingBandAdvisor HITL flow](../../assets/demo/consensus-vote-stuffing.gif)

Offline HITL advisor. Never network I/O. Closes gaps vs AutoGen/CrewAI/LangGraph consensus vote-stuffing band advisors.

Optional polish via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

Distinct from `CriticCollusionBandAdvisor` / `CriticAgreementEntropyAdvisor`.

## Usage

```python
from multi_bot_agentic.consensus_vote_stuffing import ConsensusVoteStuffingBandAdvisor

status = ConsensusVoteStuffingBandAdvisor().advise("s1", stuffing_score=0.1)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Always `requires_human_review=True`. No HTTP. Humans decide.
