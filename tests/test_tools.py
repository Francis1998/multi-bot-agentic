"""Tests for built-in tool adapters."""

from __future__ import annotations

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.checklist import ChecklistTool


def test_checklist_tool_generates_deterministic_items() -> None:
    """ChecklistTool returns a stable audit-friendly checklist."""

    result = ChecklistTool().execute(ToolInvocation(tool_name="checklist", arguments={"text": "agent platform launch"}))

    assert result.ok is True
    assert result.metadata["items"] == 5
    assert "Confirm safety policy" in result.content
