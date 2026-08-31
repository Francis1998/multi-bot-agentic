"""Bitcoin-alphabet Base58 encode/decode tool.

Agents often need to move opaque payloads through human-typed channels that
forbid ambiguous lookalikes (0/O/I/l). Asking a model to Base58-encode bytes is
unreliable. This tool encodes or decodes UTF-8 text with the Bitcoin Base58
alphabet. It never executes code and never makes network requests. Safe for
GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.
"""

from __future__ import annotations

from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_DEFAULT_MODE: Final[str] = "encode"
_ALLOWED_MODES: Final[frozenset[str]] = frozenset({"encode", "decode"})
# Bitcoin Base58 alphabet (no 0, O, I, or l).
_ALPHABET: Final[str] = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_ALPHABET_INDEX: Final[dict[str, int]] = {char: index for index, char in enumerate(_ALPHABET)}
_BASE: Final[int] = 58


class Base58Tool:
    """Encode text to Bitcoin Base58 or decode Base58 back to text."""

    name = "base58"
    description = (
        "Encodes or decodes text via Bitcoin-alphabet Base58 (mode encode|decode); max 20_000 chars; no network."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Encode or decode the document in the invocation arguments.

        Args:
            invocation: Tool invocation whose ``text`` or ``data`` argument
                holds the document and whose optional ``mode`` argument selects
                ``encode`` (default) or ``decode``.

        Returns:
            Tool result with the transformed text, or ``ok=False`` when the
            document is empty or too long, the mode is unsupported, or decoding
            fails because the input is not valid Base58 / not valid UTF-8.
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
            return self._encode(document)
        return self._decode(document)

    def _encode(self, document: str) -> ToolResult:
        """Encode a UTF-8 document to Bitcoin Base58 text."""

        encoded = _b58encode(document.encode("utf-8"))
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=encoded,
            metadata={
                "mode": "encode",
                "alphabet": "bitcoin",
                "input_chars": len(document),
                "chars": len(encoded),
            },
        )

    def _decode(self, document: str) -> ToolResult:
        """Decode Bitcoin Base58 text back to a UTF-8 document."""

        payload = "".join(document.split())
        try:
            decoded_bytes = _b58decode(payload)
        except ValueError as exc:
            return self._fail(
                str(exc),
                {"mode": "decode", "alphabet": "bitcoin"},
            )
        try:
            decoded_text = decoded_bytes.decode("utf-8")
        except UnicodeDecodeError:
            return self._fail(
                "decoded bytes are not valid utf-8",
                {"mode": "decode", "alphabet": "bitcoin", "bytes": len(decoded_bytes)},
            )
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=decoded_text,
            metadata={
                "mode": "decode",
                "alphabet": "bitcoin",
                "bytes": len(decoded_bytes),
                "chars": len(decoded_text),
            },
        )

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)


def _b58encode(raw: bytes) -> str:
    """Encode ``raw`` bytes with the Bitcoin Base58 alphabet."""

    if not raw:
        return ""

    # Count leading zero bytes → leading '1' characters.
    leading_zeros = 0
    for byte in raw:
        if byte == 0:
            leading_zeros += 1
        else:
            break

    # Interpret remaining bytes as a big-endian integer.
    number = int.from_bytes(raw, "big")
    encoded_chars: list[str] = []
    while number > 0:
        number, remainder = divmod(number, _BASE)
        encoded_chars.append(_ALPHABET[remainder])

    return ("1" * leading_zeros) + "".join(reversed(encoded_chars))


def _b58decode(text: str) -> bytes:
    """Decode Bitcoin Base58 ``text`` to bytes.

    Raises:
        ValueError: When ``text`` contains characters outside the alphabet.
    """

    if not text:
        return b""

    leading_ones = 0
    for char in text:
        if char == "1":
            leading_ones += 1
        else:
            break

    number = 0
    for char in text:
        value = _ALPHABET_INDEX.get(char)
        if value is None:
            raise ValueError("input is not valid base58")
        number = number * _BASE + value

    if number == 0:
        return b"\x00" * leading_ones

    decoded = number.to_bytes((number.bit_length() + 7) // 8, "big")
    return (b"\x00" * leading_ones) + decoded
