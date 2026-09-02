"""Luhn checksum validate / check-digit tool.

Agents validating payment-card-like or ID digit strings need a deterministic
Luhn (mod-10) check. Models invent parity rules. This tool validates or
appends a check digit with no network access. Safe for GPT-5.5 /
Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.
"""

from __future__ import annotations

from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 2_000
_DEFAULT_MODE: Final[str] = "validate"
_ALLOWED_MODES: Final[frozenset[str]] = frozenset({"validate", "check_digit"})


class LuhnTool:
    """Validate a digit string with Luhn or append a Luhn check digit."""

    name = "luhn"
    description = (
        "Validates a digit string with the Luhn algorithm or appends a check digit "
        "(mode validate|check_digit); digits only after stripping spaces/dashes; "
        "max 2000 chars; no network."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Validate or complete a Luhn digit string.

        Args:
            invocation: Tool invocation whose ``text`` or ``number`` argument
                holds the digit string and whose optional ``mode`` argument
                selects ``validate`` (default) or ``check_digit``.

        Returns:
            Tool result with ``valid``/``true``/``false`` content for validate,
            or the completed number for check_digit; ``ok=False`` on errors.
        """

        raw = invocation.arguments.get("text")
        if raw is None:
            raw = invocation.arguments.get("number")
        if raw is None:
            return self._fail("missing required argument: text or number", {})
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
            valid = _luhn_valid(digits)
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

        check = _luhn_check_digit(digits)
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


def _luhn_checksum(digits: str) -> int:
    """Return the Luhn checksum total for a digit string."""

    total = 0
    reverse = digits[::-1]
    for index, char in enumerate(reverse):
        value = ord(char) - 48
        if index % 2 == 1:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total


def _luhn_valid(digits: str) -> bool:
    """Return whether ``digits`` passes the Luhn check."""

    if len(digits) < 2:
        return False
    return _luhn_checksum(digits) % 10 == 0


def _luhn_check_digit(payload: str) -> int:
    """Return the check digit that makes ``payload + digit`` Luhn-valid."""

    # Compute as if a trailing 0 were present, then choose digit to fix mod 10.
    checksum = _luhn_checksum(payload + "0")
    return (10 - (checksum % 10)) % 10
