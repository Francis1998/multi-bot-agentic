"""Deterministic Unicode normalization tool.

Agent runs often receive text with mixed compatibility forms — pasted API
responses, filenames, or user input that combines composed and decomposed
code points. Normalizing in-model is unreliable. This tool applies stdlib
:func:`unicodedata.normalize` with NFC, NFD, NFKC, or NFKD on bounded input
and returns the normalized text plus the form used. It never executes code and
never makes network requests. Safe for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x
/ Kimi K2 workers.
"""

from __future__ import annotations

import unicodedata
from typing import Final, Literal, cast

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_DEFAULT_FORM: Final[str] = "NFC"
_ALLOWED_FORMS: Final[frozenset[str]] = frozenset({"NFC", "NFD", "NFKC", "NFKD"})
UnicodeForm = Literal["NFC", "NFD", "NFKC", "NFKD"]


class UnicodeNormalizeTool:
    """Normalize Unicode text to NFC, NFD, NFKC, or NFKD."""

    name = "unicode_normalize"
    description = "Normalizes Unicode text via unicodedata (form NFC|NFD|NFKC|NFKD, default NFC); max 20_000 chars."

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Normalize the invocation text with the requested Unicode form.

        Args:
            invocation: Tool invocation whose ``text`` argument holds the
                document to normalize and whose optional ``form`` argument
                selects NFC (default), NFD, NFKC, or NFKD.

        Returns:
            Tool result whose ``content`` is the normalized text and whose
            metadata includes ``form`` and ``chars``, or ``ok=False`` when the
            document is empty, too large, or the form is unsupported.
        """

        document = str(invocation.arguments.get("text", ""))
        if not document:
            return self._fail("text is empty", {})
        if len(document) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"text exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(document)},
            )

        form = str(invocation.arguments.get("form", _DEFAULT_FORM)).strip().upper()
        if form not in _ALLOWED_FORMS:
            return self._fail(
                f"unsupported form: {form!r}; must be one of NFC, NFD, NFKC, NFKD",
                {"form": form},
            )

        normalized = unicodedata.normalize(cast(UnicodeForm, form), document)
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=normalized,
            metadata={
                "form": form,
                "chars": len(normalized),
                "input_chars": len(document),
            },
        )

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
