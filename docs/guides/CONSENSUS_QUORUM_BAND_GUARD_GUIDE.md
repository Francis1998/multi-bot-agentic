# ConsensusQuorumBandGuard Guide

![ConsensusQuorumBandGuard HITL flow](../../assets/demo/consensus-quorum-band.gif)

Offline HITL guard/advisor. Never network I/O. Gap vs AutoGen/CrewAI/LangGraph consensus quorum band guards.

Distinct from `VoteTieBreakAdvisor` / `CriticSelfConsistencyBandGuard`.

Optional polish via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Usage

```python
from multi_bot_agentic.consensus_quorum_band import ConsensusQuorumBandGuard

status = ConsensusQuorumBandGuard().check("s1", shortfall_ratio=0.1)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Always `requires_human_review=True`. Humans decide.
