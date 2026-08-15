"""Deterministic MIME attachment size inspection tool.

Agents sometimes need attachment byte sizes for routing or quota checks without
copying message bodies or attachment bytes into the next model turn. This tool
parses a bounded raw MIME message with the stdlib :mod:`email` package and
returns only filename/size metadata from Content-Disposition ``filename`` or
Content-Type ``name`` parameters. Sizes use ``Content-Length`` when present,
otherwise decoded payload byte length. It never returns payloads, writes
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


class MimeAttachmentSizesTool:
    """Return attachment filenames and byte sizes from a raw MIME message."""

    name = "mime_attachment_sizes"
    description = (
        "Parses raw MIME into a JSON list of attachment filename/size objects without payloads; max 20_000 chars."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Parse raw MIME and return attachment filename/size metadata only."""

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

        attachments: list[dict[str, object]] = []
        for part in parts:
            filename = part.get_filename()
            if filename is None:
                continue
            attachments.append(
                {
                    "filename": str(filename),
                    "size": _attachment_size(part),
                }
            )

        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=json.dumps(attachments, indent=2, ensure_ascii=False) + "\n",
            metadata={
                "attachment_count": len(attachments),
                "part_count": len(parts) - 1,
                "chars": len(raw),
            },
        )

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)


def _attachment_size(part: Message) -> int:
    """Return attachment size from Content-Length or decoded payload bytes."""

    content_length = part.get("Content-Length")
    if content_length is not None:
        try:
            return int(str(content_length).strip())
        except ValueError:
            pass

    payload = part.get_payload(decode=True)
    if isinstance(payload, bytes):
        return len(payload)
    if isinstance(payload, str):
        return len(payload.encode("utf-8", errors="replace"))
    if payload is None:
        return 0
    return len(str(payload).encode("utf-8", errors="replace"))
