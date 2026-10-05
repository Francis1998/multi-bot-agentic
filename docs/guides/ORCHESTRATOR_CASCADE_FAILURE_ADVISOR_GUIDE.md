# OrchestratorCascadeFailureAdvisor Guide

![OrchestratorCascadeFailureAdvisor HITL flow](../../assets/demo/orchestrator-cascade-failure-advisor.gif)

Offline HITL guard/advisor. Never auto-acts. Closes closed-UI gaps vs AutoGen/CrewAI/LangGraph orchestrator cascade-failure advisors.

Optional later polish via **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

Distinct from ``OrchestratorFairnessAgingAdvisor`` and ``DeadLetterToolQueue``.

## Usage

```python
from multi_bot_agentic.orchestrator_cascade_failure import OrchestratorCascadeFailureAdvisor

status = OrchestratorCascadeFailureAdvisor().advise("session-1", cascade_depth=3.0)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Always `requires_human_review=True`. No HTTP. Humans decide. See `docs/SAFETY.md`.
