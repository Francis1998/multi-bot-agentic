"""Deterministic MIME Content-ID to attachment metadata map tool.

Agents sometimes need to resolve ``cid:`` references in multipart messages to
attachment filenames and content types without copying payloads into the next
model turn. This tool parses a bounded raw MIME message with the stdlib
:mod:`email` package and returns only a JSON map from Content-ID tokens to
filename/content-type metadata. It never returns payloads, writes attachments,
executes code, or makes network requests. Safe for GPT-5.5 / Claude Sonnet 4.6 /
Gemini 3.x / Kimi K2 workers.
"""

from __future__ import annotations

import json
from email import policy
from email.message import Message
from email.parser import Parser
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_DEFAULT_CONTENT_TYPE: Final[str] = "application/octet-stream"


class MimeAttachmentCidMapTool:
    """Map MIME Content-ID values to attachment filename/content-type metadata."""

    name = "mime_attachment_cid_map"
    description = (
        "Parses raw MIME into a JSON map of Content-ID tokens to attachment "
        "filename/content_type objects without payloads; max 20_000 chars."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Parse raw MIME and return cid -> filename/content-type metadata."""

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

        mapping: dict[str, dict[str, str]] = {}
        for part in parts:
            if part.is_multipart():
                continue
            content_id = part.get("Content-ID")
            if content_id is None:
                continue
            cid = _normalize_cid(str(content_id))
            if not cid:
                return self._fail("Content-ID header is empty", {})
            if cid in mapping:
                return self._fail(
                    f"duplicate Content-ID: {cid!r}",
                    {"cid": cid},
                )
            filename = part.get_filename()
            mapping[cid] = {
                "filename": "" if filename is None else str(filename),
                "content_type": _attachment_content_type(part),
            }

        content = json.dumps(mapping, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
        if len(content) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"cid map exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(content), "input_chars": len(raw)},
            )

        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=content,
            metadata={
                "chars": len(raw),
                "mapped_count": len(mapping),
                "part_count": max(len(parts) - 1, 0),
            },
        )

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)


def _normalize_cid(value: str) -> str:
    """Strip angle brackets and surrounding whitespace from a Content-ID."""

    cid = value.strip()
    if cid.startswith("<") and cid.endswith(">") and len(cid) >= 2:
        cid = cid[1:-1].strip()
    return cid


def _attachment_content_type(part: Message) -> str:
    """Return the declared media type or the safe binary default."""

    if part.get("Content-Type") is None:
        return _DEFAULT_CONTENT_TYPE
    return part.get_content_type()
