"""Deterministic MIME Content-Disposition inspection tool.

Agents sometimes need attachment/inline disposition metadata for routing
without copying message bodies or attachment bytes into the next model turn.
This tool parses a bounded raw MIME message with the stdlib :mod:`email` package
and returns only Content-Disposition filename and disposition values. It never
returns payloads, writes attachments, executes code, or makes network requests.
Safe for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.
"""

from __future__ import annotations

import json
from email import policy
from email.parser import Parser
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000


class MimeAttachmentDispositionTool:
    """Return filename/disposition metadata from MIME Content-Disposition."""

    name = "mime_attachment_disposition"
    description = (
        "Parses raw MIME into a JSON list of Content-Disposition filename/disposition "
        "objects without payloads; max 20_000 chars."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Parse raw MIME and return Content-Disposition metadata only."""

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

        dispositions: list[dict[str, str | None]] = []
        for part in parts:
            disposition = part.get_content_disposition()
            if disposition is None:
                continue
            filename = part.get_param("filename", header="content-disposition")
            dispositions.append(
                {
                    "filename": str(filename) if filename is not None else None,
                    "disposition": disposition,
                }
            )

        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=json.dumps(dispositions, indent=2, ensure_ascii=False) + "\n",
            metadata={
                "disposition_count": len(dispositions),
                "part_count": len(parts) - 1,
                "chars": len(raw),
            },
        )

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
