"""ASCII85 / Base85 encode-decode tool.

Agents often need denser-than-Base64 opaque encodings for binary-safe text
handoffs. Models invent alphabets. This tool uses stdlib ``base64.a85``
(Adobe ASCII85) with no network access. Safe for GPT-5.5 / Claude Sonnet 4.6 /
Gemini 3.x / Kimi K2 workers.
"""

from __future__ import annotations

import base64
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_DEFAULT_MODE: Final[str] = "encode"
_ALLOWED_MODES: Final[frozenset[str]] = frozenset({"encode", "decode"})


class Base85Tool:
    """Encode text to ASCII85/Base85 or decode Base85 back to text."""

    name = "base85"
    description = "Encodes or decodes text via Adobe ASCII85/Base85 (mode encode|decode); max 20_000 chars; no network."

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Encode or decode the document in the invocation arguments.

        Args:
            invocation: Tool invocation whose ``text`` or ``data`` argument
                holds the document and whose optional ``mode`` argument selects
                ``encode`` (default) or ``decode``.

        Returns:
            Tool result with the transformed text, or ``ok=False`` when the
            document is empty or too long, the mode is unsupported, or decoding
            fails.
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

        mode = str(invocation.arguments.get("mode", _DEFAULT_MODE)).strip().lower()
        if mode not in _ALLOWED_MODES:
            supported = ", ".join(sorted(_ALLOWED_MODES))
            return self._fail(
                f"unsupported mode: {mode!r}; supported: {supported}",
                {"mode": mode},
            )

        if mode == "encode":
            encoded = base64.a85encode(document.encode("utf-8")).decode("ascii")
            return ToolResult(
                tool_name=self.name,
                ok=True,
                content=encoded,
                metadata={
                    "mode": "encode",
                    "alphabet": "ascii85",
                    "input_chars": len(document),
                    "chars": len(encoded),
                },
            )

        payload = "".join(document.split())
        try:
            decoded_bytes = base64.a85decode(payload)
            decoded_text = decoded_bytes.decode("utf-8")
        except (ValueError, UnicodeDecodeError) as exc:
            return self._fail(
                f"base85 decode failed: {exc}",
                {"mode": "decode", "alphabet": "ascii85"},
            )
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=decoded_text,
            metadata={
                "mode": "decode",
                "alphabet": "ascii85",
                "bytes": len(decoded_bytes),
                "chars": len(decoded_text),
            },
        )

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
