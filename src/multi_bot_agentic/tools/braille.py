"""Unicode Braille encode / decode tool.

Agents need a deterministic ASCII↔Braille codec for accessibility demos and
puzzle pipelines. Models invent arbitrary mappings. This tool maps ASCII bytes
onto the Unicode Braille Patterns block (U+2800+) and back, with no network.
Safe for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.
"""

from __future__ import annotations

from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 2_000
_DEFAULT_MODE: Final[str] = "encode"
_ALLOWED_MODES: Final[frozenset[str]] = frozenset({"encode", "decode"})
_BRAILLE_BASE: Final[int] = 0x2800
_ASCII_MAX: Final[int] = 0x7F


class BrailleTool:
    """Encode ASCII text to Unicode Braille or decode Braille back to ASCII."""

    name = "braille"
    description = (
        "Encodes ASCII text to Unicode Braille (U+2800 block) or decodes "
        "(mode encode|decode); max 2000 chars; no network."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Encode or decode Braille for the invocation arguments.

        Args:
            invocation: Tool invocation whose ``text`` or ``data`` argument
                holds the document and whose optional ``mode`` argument selects
                ``encode`` (default) or ``decode``.

        Returns:
            Tool result with transformed text, or ``ok=False`` on validation errors.
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
            try:
                content = _encode_braille(document)
            except ValueError as exc:
                return self._fail(str(exc), {"mode": mode, "chars": len(document)})
        else:
            try:
                content = _decode_braille(document)
            except ValueError as exc:
                return self._fail(str(exc), {"mode": mode, "chars": len(document)})

        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=content,
            metadata={"mode": mode, "chars": len(document), "out_chars": len(content)},
        )

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)


def _encode_braille(text: str) -> str:
    """Map each ASCII code point to U+2800 + ord(ch)."""

    out: list[str] = []
    for ch in text:
        code = ord(ch)
        if code > _ASCII_MAX:
            raise ValueError("encode requires ASCII characters only")
        out.append(chr(_BRAILLE_BASE + code))
    return "".join(out)


def _decode_braille(text: str) -> str:
    """Map each U+2800..U+287F Braille cell back to an ASCII character."""

    out: list[str] = []
    for ch in text:
        code = ord(ch)
        if code < _BRAILLE_BASE or code > _BRAILLE_BASE + _ASCII_MAX:
            raise ValueError("decode requires Unicode Braille characters (U+2800..U+287F)")
        out.append(chr(code - _BRAILLE_BASE))
    return "".join(out)
