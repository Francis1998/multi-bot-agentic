"""Base interface for tool adapters."""

from __future__ import annotations

from typing import Protocol

from multi_bot_agentic.models import ToolInvocation, ToolResult


class ToolAdapter(Protocol):
    """Protocol implemented by all executable tools."""

    name: str
    description: str

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Execute the tool invocation.

        Args:
            invocation: Tool invocation details.

        Returns:
            Tool execution result.
        """
