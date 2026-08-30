"""American Soundex phonetic code tool for fuzzy name matching.

CrewAI / LangChain-style agent toolkits often need a deterministic phonetic
fingerprint when reconciling person names or vendor labels. Asking a model to
compute Soundex is unreliable. This tool returns the classic 4-character
American Soundex code for a string. It never executes code and never makes
network requests. Safe for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2
workers.
"""

from __future__ import annotations

from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_CHARS: Final[int] = 2_000
_MAPPING: Final[tuple[tuple[str, str], ...]] = (
    ("BFPV", "1"),
    ("CGJKQSXZ", "2"),
    ("DT", "3"),
    ("L", "4"),
    ("MN", "5"),
    ("R", "6"),
)


class SoundexTool:
    """Compute the American Soundex phonetic code for a string."""

    name = "soundex"
    description = (
        "Returns American Soundex phonetic code for text (max 2000 chars); "
        "4-character code; no network."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Return the Soundex code for ``text``.

        Args:
            invocation: Tool invocation with required ``text`` string.

        Returns:
            Tool result whose ``content`` is the 4-character Soundex code, or
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

        code = self._soundex(text)
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=code,
            metadata={"soundex": code, "chars": len(text)},
        )

    @staticmethod
    def _soundex(text: str) -> str:
        """Compute American Soundex for ``text``."""

        letters = [ch.upper() for ch in text if ch.isalpha()]
        if not letters:
            return "0000"

        first_letter = letters[0]
        coded: list[str] = [first_letter]
        previous_code = _digit_for(first_letter)

        for char in letters[1:]:
            digit = _digit_for(char)
            if digit:
                if digit != previous_code:
                    coded.append(digit)
                    previous_code = digit
            elif char not in "HW":
                previous_code = ""

        compact = coded[0] + "".join(ch for ch in coded[1:] if ch.isdigit())
        return compact[:4].ljust(4, "0")

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)


def _digit_for(char: str) -> str:
    """Map a letter to its Soundex digit, or empty for vowels and H/W."""

    upper = char.upper()
    for letters, digit in _MAPPING:
        if upper in letters:
            return digit
    return ""
