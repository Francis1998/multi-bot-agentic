# VoteTieBreakPolicy Guide

![VoteTieBreakPolicy HITL flow](../../assets/demo/vote-tie-break-policy.gif)

Offline HITL tie-break for multi-bot votes. Never performs network I/O.

Optional polish via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

Distinct from `BotVoteConsensusAggregator` and `ConsensusConfidenceBandAdvisor`.

## Usage

```python
from multi_bot_agentic.vote_tie_break import VoteTieBreakPolicy

result = VoteTieBreakPolicy().resolve(
    "sess-1",
    tied_options=["plan-a", "plan-b"],
    policy="lexicographic",
)
assert result.requires_human_review is True
print(result.winner, result.band)
```
