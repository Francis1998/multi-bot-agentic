"""Base32 encode/decode tool.

Agents often need to move opaque payloads through case-insensitive or
human-typed channels (TOTP secrets, Crockford-adjacent labels, text-only
relays). Asking a model to Base32-encode bytes is unreliable. This tool uses
stdlib :func:`base64.b32encode` / :func:`base64.b32decode` with the standard
RFC 4648 alphabet. It never executes code and never makes network requests.
Safe for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.
"""

from __future__ import annotations

import base64
import binascii
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_DEFAULT_MODE: Final[str] = "encode"
_ALLOWED_MODES: Final[frozenset[str]] = frozenset({"encode", "decode"})


class Base32EncodeTool:
    """Encode text to Base32 or decode Base32 back to text."""

    name = "base32_encode"
    description = (
        "Encodes or decodes text via stdlib base64.b32encode/b32decode "
        "(mode encode|decode; standard alphabet); max 20_000 chars."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Encode or decode the document in the invocation text.

        Args:
            invocation: Tool invocation whose ``text`` argument holds the
                document and whose optional ``mode`` argument selects
                ``encode`` (default) or ``decode``.

        Returns:
            Tool result with the transformed text, or ``ok=False`` when the
            document is empty or too long, the mode is unsupported, or decoding
            fails because the input is not valid Base32 / not valid UTF-8.
        """

        document = str(invocation.arguments.get("text", ""))
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
            return self._encode(document)
        return self._decode(document)

    def _encode(self, document: str) -> ToolResult:
        """Encode a UTF-8 document to standard Base32 text."""

        encoded = base64.b32encode(document.encode("utf-8")).decode("ascii")
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=encoded,
            metadata={
                "mode": "encode",
                "alphabet": "standard",
                "input_chars": len(document),
                "chars": len(encoded),
            },
        )

    def _decode(self, document: str) -> ToolResult:
        """Decode standard Base32 text back to a UTF-8 document."""

        payload = "".join(document.split())
        try:
            decoded_bytes = base64.b32decode(payload, casefold=True)
        except (binascii.Error, ValueError):
            return self._fail(
                "input is not valid base32",
                {"mode": "decode", "alphabet": "standard"},
            )
        try:
            decoded_text = decoded_bytes.decode("utf-8")
        except UnicodeDecodeError:
            return self._fail(
                "decoded bytes are not valid utf-8",
                {"mode": "decode", "alphabet": "standard", "bytes": len(decoded_bytes)},
            )
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=decoded_text,
            metadata={
                "mode": "decode",
                "alphabet": "standard",
                "bytes": len(decoded_bytes),
                "chars": len(decoded_text),
            },
        )

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
