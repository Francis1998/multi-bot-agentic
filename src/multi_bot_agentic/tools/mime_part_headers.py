"""Deterministic MIME header inspection tool.

Agents sometimes need routing metadata from raw email without copying message
bodies or attachment content into the next model turn. This tool parses a
bounded raw MIME message with the stdlib :mod:`email` package and emits only
top-level and child-part header maps. It never returns payloads, executes code,
writes attachments, or makes network requests. Safe for GPT-5.5 / Claude
Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.
"""

from __future__ import annotations

import json
from email import policy
from email.message import Message
from email.parser import Parser
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000


class MimePartHeadersTool:
    """Return top-level and per-part MIME header maps."""

    name = "mime_part_headers"
    description = (
        "Parses a raw MIME message into JSON top-level and per-part header maps "
        "without payload content; max 20_000 chars."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Parse the invocation's raw MIME message and return its headers."""

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

        child_parts = list(message.walk())[1:]
        document = {
            "top_level": _header_map(message),
            "parts": [
                {
                    "index": index,
                    "headers": _header_map(part),
                }
                for index, part in enumerate(child_parts, start=1)
            ],
        }
        content = json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=content,
            metadata={
                "top_level_header_count": len(message.items()),
                "part_count": len(child_parts),
                "chars": len(raw),
            },
        )

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)


def _header_map(message: Message) -> dict[str, str | list[str]]:
    """Return decoded headers while preserving repeated header values."""

    headers: dict[str, str | list[str]] = {}
    names_by_casefold: dict[str, str] = {}
    for name, value in message.items():
        folded_name = name.casefold()
        output_name = names_by_casefold.setdefault(folded_name, name)
        text_value = str(value)
        previous = headers.get(output_name)
        if previous is None:
            headers[output_name] = text_value
        elif isinstance(previous, list):
            previous.append(text_value)
        else:
            headers[output_name] = [previous, text_value]
    return headers
