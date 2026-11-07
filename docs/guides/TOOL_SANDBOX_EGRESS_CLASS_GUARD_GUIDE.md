# ToolSandboxEgressClassGuard Guide

![ToolSandboxEgressClassGuard](../../assets/demo/tool-sandbox-egress-class-guard.gif)

Closes AutoGen / CrewAI / LangGraph tool sandbox egress class controls gaps.

Optional later polish via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

Distinct from `ToolPermissionAllowlist` and `ToolInvocationDeadlineGuard`.

## Usage

```python
from multi_bot_agentic.tool_sandbox_egress import ToolSandboxEgressClassGuard

status = ToolSandboxEgressClassGuard(max_allowed="local").check("session-1", tool_name="fetch", egress_class="network")
assert status.requires_human_review is True
print(status.band)
```

## Safety

Always `requires_human_review=True`. No HTTP. Humans decide.
