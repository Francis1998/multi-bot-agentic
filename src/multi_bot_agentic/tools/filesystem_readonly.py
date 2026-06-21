"""Read-only filesystem tool with root containment."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.models import ToolInvocation, ToolResult


class ReadOnlyFileTool:
    """Read files under a configured root without shell execution."""

    name = "readonly_file"
    description = "Reads a text file below the configured project root."

    def __init__(self, root: Path) -> None:
        """Initialize the tool.

        Args:
            root: Directory that bounds readable paths.
        """

        self.root = root.resolve()

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Read a file under the configured root.

        Args:
            invocation: Tool invocation details.

        Returns:
            Tool result containing file text or a denial message.
        """

        raw_path = str(invocation.arguments.get("path", ""))
        candidate = (self.root / raw_path).resolve()
        if not candidate.is_relative_to(self.root):
            return ToolResult(
                tool_name=self.name,
                ok=False,
                content="path is outside the configured root",
                metadata={"path": raw_path},
            )
        if not candidate.is_file():
            return ToolResult(
                tool_name=self.name,
                ok=False,
                content="path is not a readable file",
                metadata={"path": raw_path},
            )
        text = candidate.read_text(encoding="utf-8")[:4000]
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=text,
            metadata={"path": raw_path, "chars": len(text)},
        )
