"""Deterministic ZIP archive listing tool.

Agent runs sometimes receive small ZIP payloads as base64 blobs — export bundles,
attachment previews, or relayed tool output — and need member metadata before
choosing a parser. This tool lists ZIP entry names, uncompressed sizes,
compressed sizes, and timestamps via the standard-library :mod:`zipfile` module.
It never extracts members, never executes archive contents, and rejects invalid
or oversized input. Safe for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2
workers.
"""

from __future__ import annotations

import base64
import binascii
import io
import json
from typing import Final
from zipfile import BadZipFile, ZipFile

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_BASE64_CHARS: Final[int] = 20_000
_MAX_DECODED_BYTES: Final[int] = 20_000


class ZipListTool:
    """List ZIP archive member metadata from base64-encoded bytes."""

    name = "zip_list"
    description = (
        "Lists ZIP archive member metadata from base64-encoded zip bytes "
        "(name, size, compress_size, date); no extract/exec; rejects non-zip."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """List members of a base64-encoded ZIP archive.

        Args:
            invocation: Tool invocation whose ``text`` argument holds standard
                base64-encoded ZIP bytes.

        Returns:
            Tool result whose ``content`` is canonical JSON listing members, or
            ``ok=False`` when the payload is empty, too large, not valid
            base64, not a ZIP archive, or exceeds the decoded-byte cap.
        """

        encoded = str(invocation.arguments.get("text", "")).strip()
        if not encoded:
            return self._fail("document is empty", {})
        if len(encoded) > _MAX_BASE64_CHARS:
            return self._fail(
                f"document exceeds max_chars={_MAX_BASE64_CHARS}",
                {"chars": len(encoded)},
            )

        try:
            decoded = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError):
            return self._fail("document is not valid base64", {})

        if len(decoded) > _MAX_DECODED_BYTES:
            return self._fail(
                f"decoded bytes exceed max_bytes={_MAX_DECODED_BYTES}",
                {"bytes": len(decoded)},
            )

        try:
            members = self._list_members(decoded)
        except BadZipFile:
            return self._fail("document is not a valid zip archive", {"bytes": len(decoded)})

        content = json.dumps(members, indent=2, sort_keys=True) + "\n"
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=content,
            metadata={
                "member_count": len(members),
                "bytes": len(decoded),
            },
        )

    @staticmethod
    def _list_members(data: bytes) -> list[dict[str, object]]:
        """Return sorted member metadata for a ZIP byte payload."""

        with ZipFile(io.BytesIO(data)) as archive:
            members: list[dict[str, object]] = []
            for info in archive.infolist():
                members.append(
                    {
                        "name": info.filename,
                        "size": info.file_size,
                        "compress_size": info.compress_size,
                        "date": _format_zip_date(info.date_time),
                    }
                )
        members.sort(key=lambda item: str(item["name"]))
        return members

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)


def _format_zip_date(date_time: tuple[int, ...]) -> str:
    """Format a ZIP ``date_time`` tuple as an ISO-like timestamp string."""

    if len(date_time) < 6:
        return ""
    year, month, day, hour, minute, second = date_time[:6]
    return f"{year:04d}-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}:{second:02d}"
