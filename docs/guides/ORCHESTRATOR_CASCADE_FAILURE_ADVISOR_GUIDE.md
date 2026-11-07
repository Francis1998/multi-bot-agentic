# OrchestratorCascadeFailureAdvisor Guide

![OrchestratorCascadeFailureAdvisor HITL flow](../../assets/demo/orchestrator-cascade-failure-advisor.gif)

Offline HITL guard/advisor. Never auto-acts. Closes closed-UI gaps vs AutoGen/CrewAI/LangGraph orchestrator cascade-failure advisors.

Optional later polish via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

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
