"""Deterministic MIME attachment-filename inspection tool.

Agents sometimes need to identify attachment names without copying message
bodies or attachment bytes into the next model turn. This tool parses a bounded
raw MIME message with the stdlib :mod:`email` package and returns only filenames
from Content-Disposition ``filename`` or Content-Type ``name`` parameters. It
never returns payloads, writes attachments, executes code, or makes network
requests. Safe for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.
"""

from __future__ import annotations

import json
from email import policy
from email.parser import Parser
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000


class MimeAttachmentNamesTool:
    """Return attachment filenames from a raw MIME message."""

    name = "mime_attachment_names"
    description = (
        "Parses raw MIME into a JSON list of attachment filenames from filename/name "
        "parameters, without payloads; max 20_000 chars."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Parse raw MIME and return attachment filenames only."""

        raw = str(invocation.arguments.get("raw", ""))
        if not raw.strip():
            return self._fail("raw is empty", {})
        if len(raw) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"raw exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(raw)},
            )

        try:
            message = Parser(policy=policy.default).parsestr(raw)
        except (TypeError, ValueError) as exc:
            return self._fail(f"unable to parse MIME message: {exc}", {})

        parts = list(message.walk())
        defects = [str(defect) or type(defect).__name__ for part in parts for defect in part.defects]
        if defects:
            return self._fail(
                f"unable to parse MIME message: {defects[0]}",
                {"defects": defects},
            )

        filenames: list[str] = []
        for part in parts:
            filename = part.get_filename()
            if filename is not None:
                filenames.append(str(filename))

        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=json.dumps(filenames, indent=2, ensure_ascii=False) + "\n",
            metadata={
                "attachment_count": len(filenames),
                "part_count": len(parts) - 1,
                "chars": len(raw),
            },
        )

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
