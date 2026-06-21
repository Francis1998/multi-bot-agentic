"""Deterministic checklist tool for portfolio demos."""

from __future__ import annotations

from multi_bot_agentic.models import ToolInvocation, ToolResult


class ChecklistTool:
    """Create a deterministic launch checklist from a goal."""

    name = "checklist"
    description = "Creates a deterministic launch checklist from text."

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Create a checklist from the supplied text.

        Args:
            invocation: Tool invocation details.

        Returns:
            Tool result containing a deterministic checklist.
        """

        goal = str(invocation.arguments.get("text", "")).strip() or "agent launch"
        items = (
            f"Define scope for {goal}",
            "Confirm safety policy and tool allowlist",
            "Run fake-provider replay before live providers",
            "Review rationale traces for every decision",
            "Archive the sqlite event log for post-run audit",
        )
        content = "\n".join(f"- {item}" for item in items)
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=content,
            metadata={"items": len(items), "goal_chars": len(goal)},
        )
