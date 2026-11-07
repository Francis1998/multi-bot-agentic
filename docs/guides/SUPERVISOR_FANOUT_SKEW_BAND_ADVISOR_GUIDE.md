# SupervisorFanoutSkewBandAdvisor Guide

![SupervisorFanoutSkewBandAdvisor](../../assets/demo/supervisor-fanout-skew.gif)

HITL `skew_ratio` band guard.
Gap vs LangGraph/CrewAI/AutoGen supervisor fanout-skew monitors. Distinct from `OrchestratorFanoutBudgetBandAdvisor` / `CriticFanoutSkewAdvisor`.

Stack: **GPT-6.1 / Claude Sonnet 5.5 / Gemini 3.x / Kimi K3**.

## Usage

```python
from multi_bot_agentic.supervisor_fanout_skew_band import SupervisorFanoutSkewBandAdvisor

status = SupervisorFanoutSkewBandAdvisor(soft_limit=0.2, hard_limit=0.5).advise(
    "sess-1",
    skew_ratio=0.35,
)
print(status.band, status.requires_human_review)
```

## Safety

Advisory only. No network I/O. Never auto-acts. Humans decide.
