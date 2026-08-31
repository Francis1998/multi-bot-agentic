"""Classic Metaphone phonetic code tool for fuzzy name matching.

CrewAI / LangChain-style agent toolkits often need a deterministic phonetic
fingerprint beyond Soundex when reconciling person names or vendor labels.
Asking a model to compute Metaphone is unreliable. This tool returns the
classic Metaphone code (Lawrence Philips) for a string — not Double Metaphone.
It never executes code and never makes network requests. Safe for GPT-5.5 /
Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.
"""

from __future__ import annotations

from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_CHARS: Final[int] = 2_000
_VOWELS: Final[frozenset[str]] = frozenset("AEIOU")
_MISSING: Final[str] = ""


class MetaphoneTool:
    """Compute the classic Metaphone phonetic code for a string."""

    name = "metaphone"
    description = (
        "Returns classic Metaphone phonetic code for text (max 2000 chars); "
        "Lawrence Philips classic Metaphone (not Double Metaphone); no network."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Return the classic Metaphone code for ``text``.

        Args:
            invocation: Tool invocation with required ``text`` string.

        Returns:
            Tool result whose ``content`` is the Metaphone code, or
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

        code = self._metaphone(text)
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=code,
            metadata={"metaphone": code, "algorithm": "classic", "chars": len(text)},
        )

    @staticmethod
    def _metaphone(text: str) -> str:
        """Compute classic Metaphone (Lawrence Philips) for ``text``."""

        # Keep letters only; uppercase for a stable alphabet.
        word = "".join(ch for ch in text.upper() if ch.isalpha())
        if not word:
            return ""

        if word.startswith(("KN", "GN", "PN", "WR", "AE")):
            word = word[1:]

        codes: list[str] = []
        index = 0
        length = len(word)

        while index < length:
            char = word[index]
            nxt = word[index + 1] if index + 1 < length else _MISSING
            nxt2 = word[index + 2] if index + 2 < length else _MISSING
            prev = word[index - 1] if index > 0 else _MISSING

            # Skip duplicate adjacent letters except C.
            if char == nxt and char != "C":
                index += 1
                continue

            if char in _VOWELS:
                if index == 0:
                    codes.append(char)
            elif char == "B":
                # Drop trailing B after M (dumb -> TM).
                if not (prev == "M" and not nxt):
                    codes.append("B")
            elif char == "C":
                if (nxt == "I" and nxt2 == "A") or nxt == "H":
                    codes.append("X")
                    index += 1
                elif nxt in {"I", "E", "Y"}:
                    codes.append("S")
                    index += 1
                else:
                    codes.append("K")
            elif char == "D":
                if nxt == "G" and nxt2 in {"I", "E", "Y"}:
                    codes.append("J")
                    index += 2
                else:
                    codes.append("T")
            elif char in {"F", "J", "L", "M", "N", "R"}:
                codes.append(char)
            elif char == "G":
                if nxt in {"I", "E", "Y"}:
                    codes.append("J")
                elif nxt == "H" and nxt2 and nxt2 not in _VOWELS:
                    # Soft GH before a consonant: skip G (advance past handled below).
                    index += 1
                elif nxt == "N" and not nxt2:
                    index += 1
                else:
                    codes.append("K")
            elif char == "H":
                if index == 0 or nxt in _VOWELS or prev not in _VOWELS:
                    codes.append("H")
            elif char == "K":
                if prev != "C":
                    codes.append("K")
            elif char == "P":
                if nxt == "H":
                    codes.append("F")
                    index += 1
                else:
                    codes.append("P")
            elif char == "Q":
                codes.append("K")
            elif char == "S":
                if nxt == "H":
                    codes.append("X")
                    index += 1
                elif nxt == "I" and nxt2 in {"O", "A"}:
                    codes.append("X")
                    index += 2
                else:
                    codes.append("S")
            elif char == "T":
                if nxt == "I" and nxt2 in {"O", "A"}:
                    codes.append("X")
                elif nxt == "H":
                    codes.append("0")
                    index += 1
                elif not (nxt == "C" and nxt2 == "H"):
                    codes.append("T")
            elif char == "V":
                codes.append("F")
            elif char == "W":
                if index == 0 and nxt == "H":
                    codes.append("W")
                    index += 1
                elif nxt in _VOWELS:
                    codes.append("W")
            elif char == "X":
                if index == 0:
                    if nxt == "H" or (nxt == "I" and nxt2 in {"O", "A"}):
                        codes.append("X")
                    else:
                        codes.append("S")
                else:
                    codes.append("KS")
            elif char == "Y":
                if nxt in _VOWELS:
                    codes.append("Y")
            elif char == "Z":
                codes.append("S")

            index += 1

        return "".join(codes)

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
