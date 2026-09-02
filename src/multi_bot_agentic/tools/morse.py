"""International Morse code encode/decode tool.

Agents need a deterministic Morse codec for accessibility demos and puzzle
pipelines. Models invent dot-dash tables. This tool uses an explicit ITU-ish
map with `/` letter gaps and spaces as word gaps, no network. Safe for GPT-5.5 /
Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.
"""

from __future__ import annotations

from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_DEFAULT_MODE: Final[str] = "encode"
_ALLOWED_MODES: Final[frozenset[str]] = frozenset({"encode", "decode"})
_LETTER_GAP: Final[str] = " "
_WORD_GAP: Final[str] = " / "
_CHAR_TO_MORSE: Final[dict[str, str]] = {
    "A": ".-",
    "B": "-...",
    "C": "-.-.",
    "D": "-..",
    "E": ".",
    "F": "..-.",
    "G": "--.",
    "H": "....",
    "I": "..",
    "J": ".---",
    "K": "-.-",
    "L": ".-..",
    "M": "--",
    "N": "-.",
    "O": "---",
    "P": ".--.",
    "Q": "--.-",
    "R": ".-.",
    "S": "...",
    "T": "-",
    "U": "..-",
    "V": "...-",
    "W": ".--",
    "X": "-..-",
    "Y": "-.--",
    "Z": "--..",
    "0": "-----",
    "1": ".----",
    "2": "..---",
    "3": "...--",
    "4": "....-",
    "5": ".....",
    "6": "-....",
    "7": "--...",
    "8": "---..",
    "9": "----.",
    ".": ".-.-.-",
    ",": "--..--",
    "?": "..--..",
    "'": ".----.",
    "!": "-.-.--",
    "/": "-..-.",
    "(": "-.--.",
    ")": "-.--.-",
    "&": ".-...",
    ":": "---...",
    ";": "-.-.-.",
    "=": "-...-",
    "+": ".-.-.",
    "-": "-....-",
    "_": "..--.-",
    '"': ".-..-.",
    "$": "...-..-",
    "@": ".--.-.",
}
_MORSE_TO_CHAR: Final[dict[str, str]] = {code: char for char, code in _CHAR_TO_MORSE.items()}


class MorseTool:
    """Encode text to Morse or decode Morse back to text."""

    name = "morse"
    description = (
        "Encodes or decodes International Morse (mode encode|decode); "
        "letter gap space, word gap ' / '; max 20_000 chars; no network."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Encode or decode Morse for the invocation arguments.

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
                encoded = _encode_morse(document)
            except ValueError as exc:
                return self._fail(str(exc), {"mode": mode})
            return ToolResult(
                tool_name=self.name,
                ok=True,
                content=encoded,
                metadata={
                    "mode": "encode",
                    "input_chars": len(document),
                    "chars": len(encoded),
                },
            )

        try:
            decoded = _decode_morse(document)
        except ValueError as exc:
            return self._fail(str(exc), {"mode": mode})
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=decoded,
            metadata={
                "mode": "decode",
                "input_chars": len(document),
                "chars": len(decoded),
            },
        )

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)


def _encode_morse(text: str) -> str:
    """Encode plaintext to Morse with letter and word gaps."""

    words: list[str] = []
    for word in text.upper().split():
        codes: list[str] = []
        for char in word:
            code = _CHAR_TO_MORSE.get(char)
            if code is None:
                raise ValueError(f"unsupported character for Morse encode: {char!r}")
            codes.append(code)
        words.append(_LETTER_GAP.join(codes))
    return _WORD_GAP.join(words)


def _decode_morse(text: str) -> str:
    """Decode Morse with letter gaps and ``/`` word separators."""

    normalized = " ".join(text.strip().split())
    if not normalized:
        raise ValueError("morse text is empty after normalize")
    words_out: list[str] = []
    for word in normalized.split(" / "):
        chars: list[str] = []
        for code in word.split(" "):
            if not code:
                continue
            char = _MORSE_TO_CHAR.get(code)
            if char is None:
                raise ValueError(f"unsupported Morse code: {code!r}")
            chars.append(char)
        if chars:
            words_out.append("".join(chars))
    if not words_out:
        raise ValueError("morse text produced no characters")
    return " ".join(words_out)
