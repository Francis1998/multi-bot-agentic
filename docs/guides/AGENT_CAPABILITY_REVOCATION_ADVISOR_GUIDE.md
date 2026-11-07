# AgentCapabilityRevocationBandAdvisor Guide

![AgentCapabilityRevocationBandAdvisor HITL flow](../../assets/demo/agent-capability-revocation.gif)

Offline HITL advisor. Never network I/O. Closes gaps vs AutoGen/CrewAI/LangGraph agent-capability revocation band advisors.

Optional polish via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

Distinct from `ToolSandboxDnsRebindGuard` / `OrphanTaskSweeperGuard`.

## Usage

```python
from multi_bot_agentic.agent_capability_revocation import AgentCapabilityRevocationBandAdvisor

status = AgentCapabilityRevocationBandAdvisor().advise("s1", revocation_score=0.1)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Always `requires_human_review=True`. No HTTP. Humans decide.
