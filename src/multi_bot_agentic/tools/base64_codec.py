"""Base64 encode/decode tool.

Agent runs frequently need to move opaque payloads between steps: embedding a
small binary blob in a text-only channel, decoding a token relayed by an
upstream system, or normalising a value before hashing it. This tool converts
text to and from standard Base64 without ever executing code. It returns a
structured failure for empty or oversized input, an unsupported operation, or
input that is not valid Base64 / not valid UTF-8 when decoding, matching the
calculator, ``hash``, ``json_format``, and ``redact`` tool contracts.
"""

from __future__ import annotations

import base64
import binascii
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_DEFAULT_OPERATION: Final[str] = "encode"
_OPERATIONS: Final[frozenset[str]] = frozenset({"encode", "decode"})


class Base64Tool:
    """Encode text to Base64 or decode Base64 back to text."""

    name = "base64"
    description = "Encodes text to Base64 or decodes Base64 to text (operation: encode|decode)."

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Encode or decode the document in the invocation text.

        Args:
            invocation: Tool invocation whose ``text`` argument holds the
                document and whose optional ``operation`` argument selects
                ``encode`` (default) or ``decode``.

        Returns:
            Tool result with the transformed text, or ``ok=False`` and an
            explanation when the document is empty or too long, the operation is
            unsupported, or decoding fails because the input is not valid Base64
            or not valid UTF-8.
        """

        document = str(invocation.arguments.get("text", ""))
        if not document.strip():
            return ToolResult(
                tool_name=self.name,
                ok=False,
                content="document is empty",
                metadata={},
            )
        if len(document) > _MAX_DOCUMENT_CHARS:
            return ToolResult(
                tool_name=self.name,
                ok=False,
                content=f"document exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                metadata={"chars": len(document)},
            )

        operation = str(invocation.arguments.get("operation", _DEFAULT_OPERATION)).strip().lower()
        if operation not in _OPERATIONS:
            supported = ", ".join(sorted(_OPERATIONS))
            return ToolResult(
                tool_name=self.name,
                ok=False,
                content=f"unsupported operation: {operation!r}; supported: {supported}",
                metadata={"operation": operation},
            )

        if operation == "encode":
            return self._encode(document)
        return self._decode(document)

    def _encode(self, document: str) -> ToolResult:
        """Encode a UTF-8 document to standard Base64 text.

        Args:
            document: Text to encode.

        Returns:
            Tool result carrying the Base64 text.
        """

        encoded = base64.b64encode(document.encode("utf-8")).decode("ascii")
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=encoded,
            metadata={"operation": "encode", "input_chars": len(document)},
        )

    def _decode(self, document: str) -> ToolResult:
        """Decode standard Base64 text back to a UTF-8 document.

        The Base64 payload is validated strictly (``validate=True``) so stray,
        non-alphabet characters are rejected rather than silently discarded, and
        the decoded bytes must be valid UTF-8.

        Args:
            document: Base64 text to decode.

        Returns:
            Tool result carrying the decoded text, or a structured failure when
            the input is not valid Base64 or not valid UTF-8.
        """

        payload = "".join(document.split())
        try:
            decoded_bytes = base64.b64decode(payload, validate=True)
        except (binascii.Error, ValueError):
            return ToolResult(
                tool_name=self.name,
                ok=False,
                content="input is not valid base64",
                metadata={"operation": "decode"},
            )
        try:
            decoded_text = decoded_bytes.decode("utf-8")
        except UnicodeDecodeError:
            return ToolResult(
                tool_name=self.name,
                ok=False,
                content="decoded bytes are not valid utf-8",
                metadata={"operation": "decode", "bytes": len(decoded_bytes)},
            )
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=decoded_text,
            metadata={"operation": "decode", "bytes": len(decoded_bytes)},
        )
