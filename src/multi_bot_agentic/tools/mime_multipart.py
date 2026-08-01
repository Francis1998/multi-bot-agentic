"""Deterministic MIME multipart parsing tool.

Agent runs sometimes receive raw email or HTTP multipart bodies — pasted
webhook payloads, relayed MIME messages, or attachment previews — and need a
structured summary of each part before choosing a parser. Guessing boundaries
in-model is unreliable. This tool parses multipart messages via stdlib
:mod:`email` and returns a JSON summary of each part (content-type, charset,
size, payload preview). It never executes code, never extracts attachments to
disk, and never makes network requests. Safe for GPT-5.5 / Claude Sonnet 4.6 /
Gemini 3.x / Kimi K2 workers.
"""

from __future__ import annotations

import json
from email import message_from_string
from email.message import Message
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_PREVIEW_CHARS: Final[int] = 120


class MimeMultipartTool:
    """Extract a JSON summary of MIME multipart message parts."""

    name = "mime_multipart"
    description = (
        "Parses a raw MIME message and returns JSON part summaries "
        "(content-type, charset, size, payload preview); max 20_000 chars."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Parse a raw MIME message and summarize its parts.

        Args:
            invocation: Tool invocation whose ``raw`` argument holds the raw
                MIME message text.

        Returns:
            Tool result whose ``content`` is canonical JSON listing parts, or
            ``ok=False`` when the message is empty, too large, or cannot be
            parsed.
        """

        raw = str(invocation.arguments.get("raw", ""))
        if not raw.strip():
            return self._fail("raw is empty", {})
        if len(raw) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"raw exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(raw)},
            )

        try:
            message = message_from_string(raw)
        except (TypeError, ValueError) as exc:
            return self._fail(f"unable to parse MIME message: {exc}", {})

        parts = _summarize_parts(message)
        if not parts:
            return self._fail("message contains no payload parts", {})

        content = json.dumps(parts, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=content,
            metadata={
                "part_count": len(parts),
                "multipart": message.is_multipart(),
                "chars": len(raw),
            },
        )

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)


def _summarize_parts(message: Message) -> list[dict[str, object]]:
    """Return JSON-serializable summaries for each MIME payload part."""

    summaries: list[dict[str, object]] = []
    for index, part in enumerate(message.walk()):
        if part.is_multipart():
            continue

        payload_bytes = _payload_bytes(part)
        charset = part.get_content_charset()
        content_type = part.get_content_type()
        preview = payload_bytes[:_PREVIEW_CHARS].decode("utf-8", errors="replace")

        summaries.append(
            {
                "index": index,
                "content_type": content_type,
                "charset": charset,
                "size": len(payload_bytes),
                "payload_preview": preview,
            }
        )
    return summaries


def _payload_bytes(part: Message) -> bytes:
    """Return decoded payload bytes for a MIME part."""

    payload = part.get_payload(decode=True)
    if isinstance(payload, bytes):
        return payload
    if isinstance(payload, str):
        return payload.encode("utf-8", errors="replace")
    if payload is None:
        return b""
    return str(payload).encode("utf-8", errors="replace")
