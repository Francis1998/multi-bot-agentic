"""ISBN-13 validate / check-digit tool.

Agents validating book identifiers need a deterministic ISBN-13 (EAN-13)
mod-10 check. Models invent weighting rules. This tool validates or
appends a check digit with no network access. Safe for GPT-5.5 /
Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.
"""

from __future__ import annotations

from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 2_000
_DEFAULT_MODE: Final[str] = "validate"
_ALLOWED_MODES: Final[frozenset[str]] = frozenset({"validate", "check_digit"})


class Isbn13Tool:
    """Validate an ISBN-13 string or append an ISBN-13 check digit."""

    name = "isbn13"
    description = (
        "Validates an ISBN-13 (EAN-13) digit string or appends a check digit "
        "(mode validate|check_digit); digits only after stripping spaces/dashes; "
        "max 2000 chars; no network."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Validate or complete an ISBN-13 digit string.

        Args:
            invocation: Tool invocation whose ``text`` or ``isbn`` argument
                holds the digit string and whose optional ``mode`` argument
                selects ``validate`` (default) or ``check_digit``.

        Returns:
            Tool result with ``valid``/``true``/``false`` content for validate,
            or the completed ISBN for check_digit; ``ok=False`` on errors.
        """

        raw = invocation.arguments.get("text")
        if raw is None:
            raw = invocation.arguments.get("isbn")
        if raw is None:
            return self._fail("missing required argument: text or isbn", {})
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

        digits = "".join(ch for ch in document if ch not in {" ", "-"})
        if not digits or not digits.isdigit():
            return self._fail("text must contain only digits, spaces, or dashes", {"mode": mode})

        if mode == "validate":
            if len(digits) != 13:
                return ToolResult(
                    tool_name=self.name,
                    ok=True,
                    content="false",
                    metadata={
                        "mode": mode,
                        "digits": len(digits),
                        "valid": False,
                        "reason": "length_not_13",
                    },
                )
            valid = _isbn13_valid(digits)
            return ToolResult(
                tool_name=self.name,
                ok=True,
                content="true" if valid else "false",
                metadata={
                    "mode": mode,
                    "digits": len(digits),
                    "valid": valid,
                },
            )

        if len(digits) != 12:
            return self._fail(
                "check_digit mode requires exactly 12 payload digits",
                {"mode": mode, "digits": len(digits)},
            )
        check = _isbn13_check_digit(digits)
        completed = digits + str(check)
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=completed,
            metadata={
                "mode": mode,
                "digits": len(completed),
                "check_digit": check,
            },
        )

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)


def _isbn13_check_digit(payload12: str) -> int:
    """Return the ISBN-13 check digit for a 12-digit payload."""

    total = 0
    for index, char in enumerate(payload12):
        value = ord(char) - 48
        total += value if index % 2 == 0 else value * 3
    return (10 - (total % 10)) % 10


def _isbn13_valid(digits13: str) -> bool:
    """Return whether a 13-digit string passes the ISBN-13 check."""

    return _isbn13_check_digit(digits13[:12]) == (ord(digits13[12]) - 48)
