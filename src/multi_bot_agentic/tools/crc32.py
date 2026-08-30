"""CRC32 checksum tool for content-integrity agent pipelines.

Agent pipelines often need a deterministic CRC32 fingerprint when comparing
handoff blobs or cache keys. Asking a model to compute CRC32 is unreliable.
This tool returns the unsigned hexadecimal CRC32 digest of UTF-8 text via
stdlib ``zlib``. It never executes code and never makes network requests.
Safe for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.
"""

from __future__ import annotations

import zlib
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_CHARS: Final[int] = 100_000


class Crc32Tool:
    """Compute the unsigned CRC32 hex digest of UTF-8 text."""

    name = "crc32"
    description = "Returns unsigned CRC32 hex digest of UTF-8 text (max 100_000 chars); no network."

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Return the CRC32 hex digest for ``text``.

        Args:
            invocation: Tool invocation with required ``text`` string.

        Returns:
            Tool result whose ``content`` is the unsigned hex digest, or
            ``ok=False`` on validation failure.
        """

        raw_text = invocation.arguments.get("text")
        if raw_text is None:
            return self._fail("missing required argument: text", {})
        text = str(raw_text)
        if not text:
            return self._fail("text is empty", {})
        if len(text) > _MAX_CHARS:
            return self._fail(
                f"input exceeds max {_MAX_CHARS} chars",
                {"chars": len(text)},
            )

        digest = zlib.crc32(text.encode("utf-8")) & 0xFFFFFFFF
        hex_digest = format(digest, "x")
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=hex_digest,
            metadata={"crc32": hex_digest, "chars": len(text)},
        )

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
