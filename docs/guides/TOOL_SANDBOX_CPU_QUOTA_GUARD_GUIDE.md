# ToolSandboxCpuQuotaGuard Guide

![ToolSandboxCpuQuotaGuard](../../assets/demo/tool-sandbox-cpu-quota-guard.gif)

Closes AutoGen/CrewAI/LangGraph tool-sandbox CPU quota controls gaps.

Optional later polish via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

Distinct from `ToolSandboxEgressClassGuard` and `ToolArgByteBudgetGuard`.

## Usage

```python
from multi_bot_agentic.tool_sandbox_cpu_quota import ToolSandboxCpuQuotaGuard

status = ToolSandboxCpuQuotaGuard().check("session-1", cpu_percent=82.0)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Always `requires_human_review=True`. No HTTP. Humans decide.
