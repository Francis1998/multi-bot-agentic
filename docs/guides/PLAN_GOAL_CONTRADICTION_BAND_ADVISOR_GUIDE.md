# PlanGoalContradictionBandAdvisor Guide

![PlanGoalContradictionBandAdvisor HITL flow](../../assets/demo/plan-goal-contradiction-band.gif)

Offline HITL advisor. Never network I/O. Closes gaps vs AutoGen/CrewAI/LangGraph plan-goal contradiction band advisors.

Optional polish via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

Distinct from `PlannerGoalDriftGuard` / `PlanStepCycleDetectorGuard`.

## Usage

```python
from multi_bot_agentic.plan_goal_contradiction_band import PlanGoalContradictionBandAdvisor

status = PlanGoalContradictionBandAdvisor().advise("s1", contradiction_score=0.1)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Always `requires_human_review=True`. No HTTP. Humans decide.
