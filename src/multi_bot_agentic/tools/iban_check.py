"""IBAN validation tool.

Agents validating international bank account numbers need a deterministic
mod-97 check. Models miscalculate the modular arithmetic. This tool validates
an IBAN string with no network access. Safe for GPT-5.5 / Claude Sonnet 4.6 /
Gemini 3.x / Kimi K2 workers.
"""

from __future__ import annotations

from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_CHARS: Final[int] = 2_000
_MIN_IBAN_LEN: Final[int] = 15
_MAX_IBAN_LEN: Final[int] = 34


class IbanCheckTool:
    """Validate an IBAN using the mod-97 algorithm."""

    name = "iban_check"
    description = (
        "Validates an IBAN string using the ISO 13616 mod-97 algorithm; "
        "returns valid/invalid plus country code; max 2000 chars; no network."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        raw = invocation.arguments.get("iban")
        if raw is None:
            raw = invocation.arguments.get("text")
        if raw is None:
            return self._fail("missing required argument: iban or text", {})
        document = str(raw).strip().upper().replace(" ", "").replace("-", "")
        if not document:
            return self._fail("iban is empty", {})
        if len(str(raw).strip()) > _MAX_CHARS:
            return self._fail(
                f"input exceeds max_chars={_MAX_CHARS}",
                {"chars": len(str(raw).strip())},
            )

        if len(document) < _MIN_IBAN_LEN or len(document) > _MAX_IBAN_LEN:
            return self._fail(
                f"IBAN length {len(document)} outside valid range {_MIN_IBAN_LEN}-{_MAX_IBAN_LEN}",
                {"length": len(document)},
            )

        country = document[:2]
        if not country.isalpha():
            return self._fail(
                "IBAN must start with a two-letter country code",
                {"prefix": document[:2]},
            )

        if not document[2:4].isdigit():
            return self._fail(
                "IBAN positions 3-4 must be check digits",
                {"check_digits": document[2:4]},
            )

        if not document[4:].isalnum():
            return self._fail(
                "IBAN body contains invalid characters",
                {"country": country},
            )

        valid = _mod97_check(document)
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content="valid" if valid else "invalid",
            metadata={
                "valid": valid,
                "country": country,
                "length": len(document),
            },
        )

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)


def _mod97_check(iban: str) -> bool:
    """Validate IBAN via ISO 13616 mod-97 rearrangement."""

    rearranged = iban[4:] + iban[:4]
    numeric = ""
    for ch in rearranged:
        if ch.isdigit():
            numeric += ch
        else:
            numeric += str(ord(ch) - ord("A") + 10)
    return int(numeric) % 97 == 1
