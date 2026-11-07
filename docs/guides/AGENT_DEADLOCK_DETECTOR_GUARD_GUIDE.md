# AgentDeadlockDetectorGuard Guide

![AgentDeadlockDetectorGuard HITL flow](../../assets/demo/agent-deadlock-detector-guard.gif)

Offline HITL guard. Never performs network I/O.
Closes gaps vs AutoGen/CrewAI/LangGraph agent-deadlock detectors.

Optional later polish via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

Distinct from `PlanStepCycleDetectorGuard` / `OrchestratorCascadeFailureAdvisor`.

## Usage

```python
from multi_bot_agentic.agent_deadlock_detector import AgentDeadlockDetectorGuard

status = AgentDeadlockDetectorGuard().check("session-1", deadlock_score=0.35)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Always `requires_human_review=True`. No HTTP. Humans decide.
