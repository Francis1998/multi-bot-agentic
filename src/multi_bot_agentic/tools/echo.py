"""Echo tool used for deterministic demos and tests."""

from __future__ import annotations

from multi_bot_agentic.models import ToolInvocation, ToolResult


class EchoTool:
    """Safe tool that returns the supplied text."""

    name = "echo"
    description = "Echoes text back to the event log."

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Execute the echo tool.

        Args:
            invocation: Tool invocation details.

        Returns:
            Tool result containing echoed text.
        """

        text = str(invocation.arguments.get("text", ""))
        return ToolResult(tool_name=self.name, ok=True, content=text, metadata={"chars": len(text)})
