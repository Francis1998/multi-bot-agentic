# CriticTimeoutCascadeGuard Guide

![CriticTimeoutCascadeGuard HITL flow](../../assets/demo/critic-timeout-cascade.gif)

Offline HITL guard. Never network I/O. Closes gaps vs AutoGen/CrewAI/LangGraph critic-timeout cascade guards.

Optional polish via **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

Distinct from `CriticTimeoutBandAdvisor` / `OrchestratorCascadeFailureAdvisor`.

## Usage

```python
from multi_bot_agentic.critic_timeout_cascade import CriticTimeoutCascadeGuard

status = CriticTimeoutCascadeGuard().check("s1", cascade_score=0.1)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Always `requires_human_review=True`. No HTTP. Humans decide.
