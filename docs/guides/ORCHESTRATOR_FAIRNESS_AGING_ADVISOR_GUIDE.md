# OrchestratorFairnessAgingAdvisor Guide

![OrchestratorFairnessAgingAdvisor HITL flow](../../assets/demo/orchestrator-fairness-aging-advisor.gif)

Offline HITL guard/advisor. Never auto-acts. Closes closed-UI gaps vs AutoGen/CrewAI/LangGraph orchestrator fairness-aging controls.

Optional later polish via **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

Distinct from ``MultiBotLatencyBudgetAllocator`` and ``FanInSkewBandGuard``.

## Usage

```python
from multi_bot_agentic.orchestrator_fairness_aging import OrchestratorFairnessAgingAdvisor

status = OrchestratorFairnessAgingAdvisor().check("session-1", wait_age_seconds=60.0)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Always `requires_human_review=True`. No HTTP. Humans decide. See `docs/SAFETY.md`.
