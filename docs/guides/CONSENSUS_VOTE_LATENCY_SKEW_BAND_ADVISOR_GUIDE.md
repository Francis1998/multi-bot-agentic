# ConsensusVoteLatencySkewBandAdvisor Guide

![ConsensusVoteLatencySkewBandAdvisor](../../assets/demo/consensus-vote-latency-skew.gif)

Offline HITL `skew_ratio` band advisor.
Gap vs LangGraph/CrewAI/AutoGen consensus vote latency-skew monitors. Distinct from `ConsensusQuorumStallAdvisor` / `ConsensusConfidenceBandAdvisor`.

Stack: **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Usage

```python
from multi_bot_agentic.consensus_vote_latency_skew_band import ConsensusVoteLatencySkewBandAdvisor

status = ConsensusVoteLatencySkewBandAdvisor().advise("session-1", skew_ratio=0.85)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Advisory only. No network I/O. Humans decide.
