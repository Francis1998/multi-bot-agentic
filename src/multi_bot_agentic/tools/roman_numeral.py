"""Roman numeral encode / decode tool.

Agents converting integers to Roman numerals (or back) need a deterministic
codec. Models invent subtractive pairs. This tool encodes 1..3999 and
decodes standard Roman strings with no network access. Safe for GPT-5.5 /
Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.
"""

from __future__ import annotations

from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 2_000
_DEFAULT_MODE: Final[str] = "encode"
_ALLOWED_MODES: Final[frozenset[str]] = frozenset({"encode", "decode"})
_MIN_VALUE: Final[int] = 1
_MAX_VALUE: Final[int] = 3999
_ROMAN_MAP: Final[tuple[tuple[int, str], ...]] = (
    (1000, "M"),
    (900, "CM"),
    (500, "D"),
    (400, "CD"),
    (100, "C"),
    (90, "XC"),
    (50, "L"),
    (40, "XL"),
    (10, "X"),
    (9, "IX"),
    (5, "V"),
    (4, "IV"),
    (1, "I"),
)
_ROMAN_VALUES: Final[dict[str, int]] = {
    "I": 1,
    "V": 5,
    "X": 10,
    "L": 50,
    "C": 100,
    "D": 500,
    "M": 1000,
}


class RomanNumeralTool:
    """Encode integers to Roman numerals or decode Roman strings."""

    name = "roman_numeral"
    description = (
        "Encodes integers 1..3999 to Roman numerals or decodes standard Roman "
        "strings (mode encode|decode); max 2000 chars; no network."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Encode or decode a Roman numeral.

        Args:
            invocation: Tool invocation whose ``text`` / ``value`` / ``number``
                argument holds the input and whose optional ``mode`` argument
                selects ``encode`` (default) or ``decode``.

        Returns:
            Tool result with Roman string or decimal integer content;
            ``ok=False`` on errors.
        """

        raw = invocation.arguments.get("text")
        if raw is None:
            raw = invocation.arguments.get("value")
        if raw is None:
            raw = invocation.arguments.get("number")
        if raw is None:
            return self._fail("missing required argument: text, value, or number", {})
        document = str(raw).strip()
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
                number = int(document)
            except ValueError:
                return self._fail("encode mode requires an integer", {"mode": mode})
            if number < _MIN_VALUE or number > _MAX_VALUE:
                return self._fail(
                    f"encode mode requires {_MIN_VALUE}..{_MAX_VALUE}",
                    {"mode": mode, "value": number},
                )
            roman = _to_roman(number)
            return ToolResult(
                tool_name=self.name,
                ok=True,
                content=roman,
                metadata={"mode": mode, "value": number, "roman": roman},
            )

        try:
            value = _from_roman(document)
        except ValueError as exc:
            return self._fail(str(exc), {"mode": mode})
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=str(value),
            metadata={"mode": mode, "value": value, "roman": document.upper()},
        )

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)


def _to_roman(number: int) -> str:
    """Convert an integer in 1..3999 to a Roman numeral string."""

    remaining = number
    parts: list[str] = []
    for value, glyph in _ROMAN_MAP:
        while remaining >= value:
            parts.append(glyph)
            remaining -= value
    return "".join(parts)


def _from_roman(roman: str) -> int:
    """Decode a standard Roman numeral string to an integer.

    Raises:
        ValueError: If the string is not a valid standard Roman numeral.
    """

    text = roman.strip().upper()
    if not text or any(ch not in _ROMAN_VALUES for ch in text):
        raise ValueError("decode mode requires a standard Roman numeral string")
    total = 0
    index = 0
    length = len(text)
    while index < length:
        value = _ROMAN_VALUES[text[index]]
        if index + 1 < length:
            next_value = _ROMAN_VALUES[text[index + 1]]
            if next_value > value:
                total += next_value - value
                index += 2
                continue
        total += value
        index += 1
    if total < _MIN_VALUE or total > _MAX_VALUE or _to_roman(total) != text:
        raise ValueError("decode mode requires a canonical Roman numeral")
    return total
