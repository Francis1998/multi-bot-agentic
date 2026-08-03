"""Line-number annotation tool for agent text handoffs.

Agents often need stable line numbers when quoting logs, diffs, or source
snippets back to a language model. Asking the model to invent line numbers
drifts across turns. This tool prefixes each line with a 1-based index using
stdlib string ops only. It never executes code and never makes network
requests. Safe for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2.
"""

from __future__ import annotations

from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_MAX_LINES: Final[int] = 2_000
_DEFAULT_SEPARATOR: Final[str] = "| "
_DEFAULT_START: Final[int] = 1


class LineNumberTool:
    """Annotate text lines with 1-based line numbers."""

    name = "line_number"
    description = "Prefixes each text line with a 1-based line number (optional start/separator); max 20_000 chars."

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Annotate each line with a line number.

        Args:
            invocation: Tool invocation whose ``text`` argument holds the
                document, optional ``start`` is the first line number (default
                1), and optional ``separator`` sits between the number and the
                line (default ``"| "``).

        Returns:
            Tool result with numbered text, or ``ok=False`` when input is empty,
            oversized, or arguments are invalid.
        """

        raw_text = invocation.arguments.get("text", "")
        document = str(raw_text)
        if not document.strip():
            return self._fail("text is empty", {})
        if len(document) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"text exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(document)},
            )

        start_raw = invocation.arguments.get("start", _DEFAULT_START)
        try:
            start = int(str(start_raw).strip())
        except ValueError:
            return self._fail(
                f"start must be an integer, got {start_raw!r}",
                {"start": str(start_raw)},
            )
        if start < 0:
            return self._fail("start must be >= 0", {"start": start})

        separator = str(invocation.arguments.get("separator", _DEFAULT_SEPARATOR))
        if "\n" in separator or "\r" in separator:
            return self._fail("separator must not contain newlines", {})

        # Preserve whether the original ended with a newline.
        ends_with_newline = document.endswith("\n")
        lines = document.splitlines()
        if len(lines) > _MAX_LINES:
            return self._fail(
                f"text exceeds max_lines={_MAX_LINES}",
                {"lines": len(lines)},
            )

        width = len(str(start + len(lines) - 1)) if lines else 1
        numbered = [f"{str(start + index).rjust(width)}{separator}{line}" for index, line in enumerate(lines)]
        content = "\n".join(numbered)
        if ends_with_newline:
            content += "\n"
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=content,
            metadata={
                "lines": len(lines),
                "start": start,
                "chars": len(content),
            },
        )

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
