"""NATO phonetic alphabet tool.

Agents spelling out identifiers, codes, or passwords need a deterministic
NATO phonetic mapping. Models hallucinate phonetic words. This tool converts
text to/from NATO phonetic alphabet with no network access. Safe for GPT-5.5 /
Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.
"""

from __future__ import annotations

from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_CHARS: Final[int] = 2_000

_NATO: Final[dict[str, str]] = {
    "A": "Alfa",
    "B": "Bravo",
    "C": "Charlie",
    "D": "Delta",
    "E": "Echo",
    "F": "Foxtrot",
    "G": "Golf",
    "H": "Hotel",
    "I": "India",
    "J": "Juliet",
    "K": "Kilo",
    "L": "Lima",
    "M": "Mike",
    "N": "November",
    "O": "Oscar",
    "P": "Papa",
    "Q": "Quebec",
    "R": "Romeo",
    "S": "Sierra",
    "T": "Tango",
    "U": "Uniform",
    "V": "Victor",
    "W": "Whiskey",
    "X": "X-ray",
    "Y": "Yankee",
    "Z": "Zulu",
    "0": "Zero",
    "1": "One",
    "2": "Two",
    "3": "Three",
    "4": "Four",
    "5": "Five",
    "6": "Six",
    "7": "Seven",
    "8": "Eight",
    "9": "Niner",
}

_NATO_REVERSE: Final[dict[str, str]] = {v.upper(): k for k, v in _NATO.items()}

_DEFAULT_MODE: Final[str] = "encode"
_ALLOWED_MODES: Final[frozenset[str]] = frozenset({"encode", "decode"})


class NatoPhoneticTool:
    """Convert text to/from NATO phonetic alphabet."""

    name = "nato_phonetic"
    description = (
        "Converts text to NATO phonetic alphabet (encode) or phonetic words back "
        "to text (decode); non-alpha/digit chars passed through; max 2000 chars; "
        "no network."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        raw = invocation.arguments.get("text")
        if raw is None:
            return self._fail("missing required argument: text", {})
        document = str(raw).strip()
        if not document:
            return self._fail("text is empty", {})
        if len(document) > _MAX_CHARS:
            return self._fail(
                f"text exceeds max_chars={_MAX_CHARS}",
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

    def _encode(self, text: str) -> ToolResult:
        parts: list[str] = []
        for ch in text:
            upper = ch.upper()
            if upper in _NATO:
                parts.append(_NATO[upper])
            else:
                parts.append(ch)
        result = " ".join(parts)
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=result,
            metadata={"mode": "encode", "chars": len(text)},
        )

    def _decode(self, text: str) -> ToolResult:
        words = text.split()
        parts: list[str] = []
        for word in words:
            upper = word.upper()
            if upper in _NATO_REVERSE:
                parts.append(_NATO_REVERSE[upper])
            else:
                parts.append(word)
        result = "".join(parts)
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=result,
            metadata={"mode": "decode", "chars": len(result)},
        )

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
