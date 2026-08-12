"""Deterministic whitespace-squeezing tool.

Agents often receive messy pasted observations with runs of spaces, tabs, or
newlines that waste context and break exact string matches. Asking a model to
normalize whitespace can drop meaningful blank lines or invent spacing. This
tool collapses whitespace runs to a single space, optionally preserving
newlines, with a hard input cap. It never executes code or makes network
requests. Safe for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.

The document and ``preserve_newlines`` flag may be supplied as separate
arguments or as a single ``text`` value split on ``<<<TEXT_SQUEEZE>>>``.
"""

from __future__ import annotations

import re
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_DEFAULT_PRESERVE_NEWLINES: Final[bool] = False
_SPLIT_SENTINEL: Final[str] = "<<<TEXT_SQUEEZE>>>"
_TRUTHY: Final[frozenset[str]] = frozenset({"1", "true", "yes", "on"})
_FALSY: Final[frozenset[str]] = frozenset({"0", "false", "no", "off"})
_ALL_WS: Final[re.Pattern[str]] = re.compile(r"\s+")
_HORIZONTAL_WS: Final[re.Pattern[str]] = re.compile(r"[^\S\n]+")


class TextSqueezeWsTool:
    """Collapse runs of whitespace to a single space."""

    name = "text_squeeze_ws"
    description = (
        "Collapses whitespace runs to a single space (preserve_newlines default false); "
        "accepts text+preserve_newlines or <<<TEXT_SQUEEZE>>>; max 20_000 chars."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Squeeze whitespace in the invocation text."""

        document, preserve_newlines, resolve_error = self._resolve_arguments(invocation.arguments)
        if resolve_error is not None:
            return self._fail(resolve_error, {})
        assert document is not None and preserve_newlines is not None

        if not document:
            return self._fail("text is empty", {})
        if len(document) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"text exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(document)},
            )

        squeezed = _HORIZONTAL_WS.sub(" ", document) if preserve_newlines else _ALL_WS.sub(" ", document)

        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=squeezed,
            metadata={
                "chars": len(squeezed),
                "input_chars": len(document),
                "preserve_newlines": preserve_newlines,
            },
        )

    @classmethod
    def _resolve_arguments(
        cls,
        arguments: dict[str, object],
    ) -> tuple[str | None, bool | None, str | None]:
        """Resolve text and preserve_newlines from arguments or sentinel syntax."""

        text = str(arguments.get("text", ""))
        if "preserve_newlines" in arguments:
            preserve = cls._parse_bool(arguments["preserve_newlines"])
            if preserve is None:
                return (
                    None,
                    None,
                    f"preserve_newlines must be a boolean, got {arguments['preserve_newlines']!r}",
                )
            return text, preserve, None

        if _SPLIT_SENTINEL not in text:
            return text, _DEFAULT_PRESERVE_NEWLINES, None

        document, remainder = text.split(_SPLIT_SENTINEL, maxsplit=1)
        if _SPLIT_SENTINEL in remainder:
            return None, None, "text contains more than one <<<TEXT_SQUEEZE>>> sentinel"
        if not remainder.strip():
            return document, _DEFAULT_PRESERVE_NEWLINES, None
        preserve = cls._parse_bool(remainder)
        if preserve is None:
            return None, None, f"preserve_newlines must be a boolean, got {remainder.strip()!r}"
        return document, preserve, None

    @staticmethod
    def _parse_bool(value: object) -> bool | None:
        """Coerce a boolean-like preserve_newlines argument."""

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
