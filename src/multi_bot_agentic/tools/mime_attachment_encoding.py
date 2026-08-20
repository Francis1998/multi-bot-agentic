"""Deterministic MIME attachment transfer-encoding inspection tool.

Agents sometimes need attachment transfer encodings for routing or validation
without copying message bodies or attachment bytes into another model turn.
This tool parses a bounded raw MIME message with the stdlib :mod:`email` package
and returns only decoded filenames and normalized Content-Transfer-Encoding
values for named parts. It never decodes or returns payloads, writes
attachments, executes code, or makes network requests. Safe for GPT-5.5 /
Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.
"""

from __future__ import annotations

import json
from email import policy
from email.message import Message
from email.parser import Parser
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_MAX_OUTPUT_CHARS: Final[int] = 20_000
_DEFAULT_ENCODING: Final[str] = "7bit"


class MimeAttachmentEncodingTool:
    """Return attachment filenames and Content-Transfer-Encoding values."""

    name = "mime_attachment_encoding"
    description = (
        "Parses bounded raw MIME into attachment filename/encoding objects "
        "without decoding or returning payloads; max 20_000 chars."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Parse raw MIME and return named-part transfer-encoding metadata."""

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

        attachments: list[dict[str, str]] = []
        for part in parts:
            filename = part.get_filename()
            if filename is None:
                continue
            attachments.append(
                {
                    "filename": str(filename),
                    "encoding": _transfer_encoding(part),
                }
            )

        content = json.dumps(attachments, indent=2, ensure_ascii=False) + "\n"
        if len(content) > _MAX_OUTPUT_CHARS:
            return self._fail(
                f"encoding output exceeds max_chars={_MAX_OUTPUT_CHARS}",
                {"chars": len(content), "attachment_count": len(attachments)},
            )

        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=content,
            metadata={
                "attachment_count": len(attachments),
                "part_count": len(parts) - 1,
                "chars": len(raw),
            },
        )

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)


def _transfer_encoding(part: Message) -> str:
    """Return the normalized declared encoding or RFC default."""

    value = part.get("Content-Transfer-Encoding")
    if value is None:
        return _DEFAULT_ENCODING
    normalized = str(value).strip().lower()
    return normalized or _DEFAULT_ENCODING
