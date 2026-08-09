"""Deterministic text case conversion tool.

Agent runs often need a stable case transform — lower, upper, title, snake,
kebab, or camel — before using free-form text as a key, slug segment, or
display label. Asking a language model to rewrite case is unreliable
(inconsistent word boundaries, dropped accents, invented separators). This
tool converts text via stdlib helpers with fixed case modes and a hard size
cap. It never executes code and never makes network requests. Safe for
GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.

Because the decision engine only forwards a single ``text`` payload from
``TOOL:text_case:<payload>``, the document and case mode may be supplied
either as separate ``text`` / ``case`` arguments or as a single ``text``
value split on ``<<<TEXT_CASE>>>``.
"""

from __future__ import annotations

import re
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_DEFAULT_CASE: Final[str] = "lower"
_ALLOWED_CASES: Final[frozenset[str]] = frozenset({"lower", "upper", "title", "snake", "kebab", "camel"})
_SPLIT_SENTINEL: Final[str] = "<<<TEXT_CASE>>>"
_WORD_SPLIT: Final[re.Pattern[str]] = re.compile(r"[^A-Za-z0-9]+")
_CAMEL_BOUNDARY: Final[re.Pattern[str]] = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


class TextCaseTool:
    """Convert text to a selected case style."""

    name = "text_case"
    description = (
        "Converts text case (lower|upper|title|snake|kebab|camel); max 20_000 chars; text+case or <<<TEXT_CASE>>>."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Convert the invocation text to the requested case.

        Args:
            invocation: Tool invocation whose arguments hold ``text`` and
                optional ``case`` (default ``lower``), or ``text`` split on
                ``<<<TEXT_CASE>>>`` with the case mode after the sentinel.

        Returns:
            Tool result whose ``content`` is the converted text, or
            ``ok=False`` when input is empty, oversized, or the case is
            unsupported.
        """

        document, case_mode, resolve_error = self._resolve_arguments(invocation.arguments)
        if resolve_error is not None:
            return self._fail(resolve_error, {})
        assert document is not None and case_mode is not None

        if not document:
            return self._fail("text is empty", {})
        if len(document) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"text exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(document)},
            )

        if case_mode not in _ALLOWED_CASES:
            supported = ", ".join(sorted(_ALLOWED_CASES))
            return self._fail(
                f"unsupported case: {case_mode!r}; must be one of {supported}",
                {"case": case_mode},
            )

        converted = self._convert(document, case_mode)
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=converted,
            metadata={
                "case": case_mode,
                "chars": len(converted),
            },
        )

    @classmethod
    def _resolve_arguments(
        cls,
        arguments: dict[str, object],
    ) -> tuple[str | None, str | None, str | None]:
        """Resolve document and case mode from args or a sentinel payload."""

        text = str(arguments.get("text", ""))
        if "case" in arguments:
            case_mode = str(arguments.get("case", _DEFAULT_CASE)).strip().lower()
            return text, case_mode, None

        if _SPLIT_SENTINEL in text:
            document, remainder = text.split(_SPLIT_SENTINEL, maxsplit=1)
            if _SPLIT_SENTINEL in remainder:
                return None, None, "text contains more than one <<<TEXT_CASE>>> sentinel"
            case_mode = remainder.strip().lower() or _DEFAULT_CASE
            return document, case_mode, None

        return text, _DEFAULT_CASE, None

    @classmethod
    def _convert(cls, document: str, case_mode: str) -> str:
        """Apply the selected case transform."""

        if case_mode == "lower":
            return document.lower()
        if case_mode == "upper":
            return document.upper()
        if case_mode == "title":
            return document.title()

        words = cls._words(document)
        if case_mode == "snake":
            return "_".join(words)
        if case_mode == "kebab":
            return "-".join(words)
        # camel
        if not words:
            return ""
        first, *rest = words
        return first + "".join(word[:1].upper() + word[1:] for word in rest)

    @classmethod
    def _words(cls, document: str) -> list[str]:
        """Split text into lowercase alphanumeric word runs."""

        spaced = _CAMEL_BOUNDARY.sub(" ", document)
        return [word.lower() for word in _WORD_SPLIT.split(spaced) if word]

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
