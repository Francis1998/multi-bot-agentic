"""Deterministic text dedenting tool.

Agents often receive indented code blocks, templates, or quoted observations
that need their shared leading whitespace removed before another deterministic
step. Asking a model to normalize indentation can alter content. This tool
applies stdlib :func:`textwrap.dedent` with optional outer-whitespace stripping
and a hard input cap. It never executes code or makes network requests. Safe
for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.

The document and ``strip`` flag may be supplied as separate arguments or as a
single ``text`` value split on ``<<<TEXT_DEDENT>>>``.
"""

from __future__ import annotations

import textwrap
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_DEFAULT_STRIP: Final[bool] = True
_SPLIT_SENTINEL: Final[str] = "<<<TEXT_DEDENT>>>"
_TRUTHY: Final[frozenset[str]] = frozenset({"1", "true", "yes", "on"})
_FALSY: Final[frozenset[str]] = frozenset({"0", "false", "no", "off"})


class TextDedentTool:
    """Remove common leading whitespace from text."""

    name = "text_dedent"
    description = (
        "Dedents text via textwrap.dedent with optional strip (default true); "
        "accepts text+strip or <<<TEXT_DEDENT>>>; max 20_000 chars."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Dedent invocation text and optionally strip outer whitespace."""

        document, strip, resolve_error = self._resolve_arguments(invocation.arguments)
        if resolve_error is not None:
            return self._fail(resolve_error, {})
        assert document is not None and strip is not None

        if not document:
            return self._fail("text is empty", {})
        if len(document) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"text exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(document)},
            )

        dedented = textwrap.dedent(document)
        if strip:
            dedented = dedented.strip()

        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=dedented,
            metadata={
                "strip": strip,
                "chars": len(dedented),
                "input_chars": len(document),
            },
        )

    @classmethod
    def _resolve_arguments(
        cls,
        arguments: dict[str, object],
    ) -> tuple[str | None, bool | None, str | None]:
        """Resolve text and strip mode from arguments or sentinel syntax."""

        text = str(arguments.get("text", ""))
        if "strip" in arguments:
            strip = cls._parse_bool(arguments["strip"])
            if strip is None:
                return None, None, f"strip must be a boolean, got {arguments['strip']!r}"
            return text, strip, None

        if _SPLIT_SENTINEL not in text:
            return text, _DEFAULT_STRIP, None

        document, remainder = text.split(_SPLIT_SENTINEL, maxsplit=1)
        if _SPLIT_SENTINEL in remainder:
            return None, None, "text contains more than one <<<TEXT_DEDENT>>> sentinel"
        if not remainder.strip():
            return document, _DEFAULT_STRIP, None
        strip = cls._parse_bool(remainder)
        if strip is None:
            return None, None, f"strip must be a boolean, got {remainder.strip()!r}"
        return document, strip, None

    @staticmethod
    def _parse_bool(value: object) -> bool | None:
        """Coerce a boolean-like strip argument."""

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
