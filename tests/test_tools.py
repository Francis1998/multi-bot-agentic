"""Tests for built-in tool adapters."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.checklist import ChecklistTool
from multi_bot_agentic.tools.filesystem_readonly import ReadOnlyFileTool


def test_checklist_tool_generates_deterministic_items() -> None:
    """ChecklistTool returns a stable audit-friendly checklist."""

    result = ChecklistTool().execute(ToolInvocation(tool_name="checklist", arguments={"text": "agent platform launch"}))

    assert result.ok is True
    assert result.metadata["items"] == 5
    assert "Confirm safety policy" in result.content


def test_readonly_file_tool_accepts_model_text_payload(tmp_path: Path) -> None:
    """ReadOnlyFileTool accepts payloads emitted by TOOL:name:text decisions."""

    notes_path = tmp_path / "notes.txt"
    notes_path.write_text("agent run notes", encoding="utf-8")

    tool = ReadOnlyFileTool(root=tmp_path)
    result = tool.execute(ToolInvocation(tool_name="readonly_file", arguments={"text": "notes.txt"}))

    assert result.ok is True
    assert result.content == "agent run notes"
    assert result.metadata == {"path": "notes.txt", "chars": 15}
