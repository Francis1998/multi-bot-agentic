# ToolSandboxDiskQuotaGuard Guide

![ToolSandboxDiskQuotaGuard HITL flow](../../assets/demo/tool-sandbox-disk-quota-guard.gif)

Offline HITL guard/advisor. Never auto-acts. Closes closed-UI gaps vs AutoGen/CrewAI/LangGraph tool-sandbox disk quota controls.

Optional later polish via **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

Distinct from ``ToolSandboxMemoryQuotaGuard`` and ``ToolSandboxCpuQuotaGuard``.

## Usage

```python
from multi_bot_agentic.tool_sandbox_disk_quota import ToolSandboxDiskQuotaGuard

status = ToolSandboxDiskQuotaGuard().check("session-1", disk_mb=2048.0)
assert status.requires_human_review is True
print(status.band)
```

## Safety

Always `requires_human_review=True`. No HTTP. Humans decide. See `docs/SAFETY.md`.
