"""ROT13 encode/decode tool.

Agents often need a deterministic Caesar-13 transform for puzzles and
reversible obfuscation demos. Models invent rotations. This tool applies
stdlib ``str.translate`` ROT13 with no network access. Safe for GPT-5.5 /
Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.
"""

from __future__ import annotations

import codecs
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000


class Rot13Tool:
    """Apply ROT13 to text (encode and decode are identical)."""

    name = "rot13"
    description = "Applies ROT13 to text (self-inverse encode/decode); max 20_000 chars; no network."

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Apply ROT13 to the document in the invocation arguments.

        Args:
            invocation: Tool invocation whose ``text`` or ``data`` argument
                holds the document.

        Returns:
            Tool result with ROT13 text, or ``ok=False`` when missing/empty/too long.
        """

        raw = invocation.arguments.get("text")
        if raw is None:
            raw = invocation.arguments.get("data")
        if raw is None:
            return self._fail("missing required argument: text or data", {})
        document = str(raw)
        if not document:
            return self._fail("text is empty", {})
        if len(document) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"text exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(document)},
            )

        transformed = codecs.encode(document, "rot_13")
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=transformed,
            metadata={
                "alphabet": "rot13",
                "input_chars": len(document),
                "chars": len(transformed),
            },
        )

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
