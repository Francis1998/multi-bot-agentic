"""Deterministic hexadecimal encode tool.

Agents often need a stable hex representation of a UTF-8 payload before hashing,
embedding in a text-only channel, or comparing opaque blobs. Asking a model to
encode bytes as hex can drop characters or invent casing. This tool encodes
text to a hexadecimal string with an optional uppercase form and a hard input
cap. It never executes code or makes network requests. Safe for GPT-5.5 /
Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.

The document and ``uppercase`` flag may be supplied as separate arguments or as
a single ``text`` value split on ``<<<HEX_ENCODE>>>``.
"""

from __future__ import annotations

from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_DEFAULT_UPPERCASE: Final[bool] = False
_SPLIT_SENTINEL: Final[str] = "<<<HEX_ENCODE>>>"
_TRUTHY: Final[frozenset[str]] = frozenset({"1", "true", "yes", "on"})
_FALSY: Final[frozenset[str]] = frozenset({"0", "false", "no", "off"})


class HexEncodeTool:
    """Encode text to a hexadecimal string of its UTF-8 bytes."""

    name = "hex_encode"
    description = (
        "Encodes text to hex (utf-8 bytes) with optional uppercase (default false); "
        "accepts text+uppercase or <<<HEX_ENCODE>>>; max 20_000 chars."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Encode invocation text to hexadecimal."""

        document, uppercase, resolve_error = self._resolve_arguments(invocation.arguments)
        if resolve_error is not None:
            return self._fail(resolve_error, {})
        assert document is not None and uppercase is not None

        if not document:
            return self._fail("text is empty", {})
        if len(document) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"text exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(document)},
            )

        encoded = document.encode("utf-8").hex()
        if uppercase:
            encoded = encoded.upper()

        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=encoded,
            metadata={
                "chars": len(encoded),
                "input_chars": len(document),
                "uppercase": uppercase,
            },
        )

    @classmethod
    def _resolve_arguments(
        cls,
        arguments: dict[str, object],
    ) -> tuple[str | None, bool | None, str | None]:
        """Resolve text and uppercase mode from arguments or sentinel syntax."""

        text = str(arguments.get("text", ""))
        if "uppercase" in arguments:
            uppercase = cls._parse_bool(arguments["uppercase"])
            if uppercase is None:
                return None, None, f"uppercase must be a boolean, got {arguments['uppercase']!r}"
            return text, uppercase, None

        if _SPLIT_SENTINEL not in text:
            return text, _DEFAULT_UPPERCASE, None

        document, remainder = text.split(_SPLIT_SENTINEL, maxsplit=1)
        if _SPLIT_SENTINEL in remainder:
            return None, None, "text contains more than one <<<HEX_ENCODE>>> sentinel"
        if not remainder.strip():
            return document, _DEFAULT_UPPERCASE, None
        uppercase = cls._parse_bool(remainder)
        if uppercase is None:
            return None, None, f"uppercase must be a boolean, got {remainder.strip()!r}"
        return document, uppercase, None

    @staticmethod
    def _parse_bool(value: object) -> bool | None:
        """Coerce a boolean-like uppercase argument."""

        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in _TRUTHY:
                return True
            if normalized in _FALSY:
                return False
        return None

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
