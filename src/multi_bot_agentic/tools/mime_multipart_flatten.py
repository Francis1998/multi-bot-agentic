"""Deterministic nested MIME multipart flatten tool.

Email and ticket agents often receive nested multipart messages and need a
compact inventory of leaf parts before GPT-5.5 / Claude Sonnet 4.6 /
Gemini 3.x / Kimi K2 reasoning. This tool recursively walks multipart MIME and
returns JSON metadata for each leaf part without payloads. Inspired by mail
pipelines in popular agent frameworks. It never executes code or makes network
requests.
"""

from __future__ import annotations

import json
from email import policy
from email.message import Message
from email.parser import Parser
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_MAX_PARTS: Final[int] = 200
_DEFAULT_CONTENT_TYPE: Final[str] = "application/octet-stream"


class MimeMultipartFlattenTool:
    """Flatten nested multipart MIME into leaf-part metadata JSON."""

    name = "mime_multipart_flatten"
    description = (
        "Recursively flattens nested multipart MIME into a JSON array of leaf "
        "part metadata (content_type, filename, content_id, size, depth) without "
        "payloads; max 20_000 chars."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Parse raw MIME and return flattened leaf-part metadata."""

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

        defects = [str(defect) or type(defect).__name__ for part in message.walk() for defect in part.defects]
        if defects:
            return self._fail(
                f"unable to parse MIME message: {defects[0]}",
                {"defects": defects},
            )

        leaves: list[dict[str, object]] = []
        max_depth = 0
        try:
            max_depth = self._walk(message, depth=0, leaves=leaves)
        except ValueError as exc:
            return self._fail(str(exc), {"parts": len(leaves)})

        content = json.dumps(leaves, separators=(",", ":"), ensure_ascii=True)
        if len(content) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"flattened metadata exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(content), "parts": len(leaves)},
            )

        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=content,
            metadata={
                "chars": len(content),
                "input_chars": len(raw),
                "parts": len(leaves),
                "max_depth": max_depth,
            },
        )

    def _walk(self, part: Message, *, depth: int, leaves: list[dict[str, object]]) -> int:
        """Recursively collect leaf-part metadata. Returns max depth seen."""

        if part.is_multipart():
            payload = part.get_payload()
            if not isinstance(payload, list):
                return depth
            max_depth = depth
            for child in payload:
                if isinstance(child, Message):
                    child_depth = self._walk(child, depth=depth + 1, leaves=leaves)
                    if child_depth > max_depth:
                        max_depth = child_depth
            return max_depth

        if len(leaves) >= _MAX_PARTS:
            raise ValueError(f"MIME exceeds max_parts={_MAX_PARTS}")

        filename = part.get_filename()
        content_id = part.get("Content-ID")
        payload = part.get_payload(decode=True)
        if isinstance(payload, (bytes, bytearray)):
            size = len(payload)
        else:
            payload_text = part.get_payload()
            size = len(payload_text.encode("utf-8")) if isinstance(payload_text, str) else 0

        leaves.append(
            {
                "content_type": part.get_content_type() or _DEFAULT_CONTENT_TYPE,
                "filename": "" if filename is None else str(filename),
                "content_id": "" if content_id is None else str(content_id).strip(),
                "size": size,
                "depth": depth,
            }
        )
        return depth

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
