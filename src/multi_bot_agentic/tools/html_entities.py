"""HTML entity encode/decode tool.

Agents often need to escape or unescape HTML entities before rendering snippets
or comparing scraped text. Asking a language model to encode entities is
unreliable (missed ampersands, double-escaping, invented named entities). This
tool uses stdlib :mod:`html` for deterministic encode (``html.escape``) and
decode (``html.unescape``). It never executes code and never makes network
requests. Safe for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.
"""

from __future__ import annotations

import html
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_DEFAULT_MODE: Final[str] = "encode"
_ALLOWED_MODES: Final[frozenset[str]] = frozenset({"encode", "decode"})


class HtmlEntitiesTool:
    """Encode or decode HTML character entities."""

    name = "html_entities"
    description = (
        "Encodes or decodes HTML entities via stdlib html "
        "(mode encode|decode; encode optionally escapes quotes); max 20_000 chars."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Encode or decode HTML entities in the invocation text.

        Args:
            invocation: Tool invocation whose ``text`` argument holds the
                document, whose optional ``mode`` argument selects ``encode``
                (default) or ``decode``, and whose optional ``quote`` argument
                (encode only) controls whether quotes are escaped.

        Returns:
            Tool result whose ``content`` is the transformed text and whose
            metadata reports ``mode``, ``quote``, and ``chars``, or ``ok=False``
            when the document is empty, too large, or arguments are invalid.
        """

        document = str(invocation.arguments.get("text", ""))
        if not document:
            return self._fail("text is empty", {})
        if len(document) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"text exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(document)},
            )

        mode = str(invocation.arguments.get("mode", _DEFAULT_MODE)).strip().lower()
        if mode not in _ALLOWED_MODES:
            return self._fail(
                f"unsupported mode: {mode!r}; must be encode or decode",
                {"mode": mode},
            )

        quote = self._parse_bool(invocation.arguments.get("quote", True))
        if quote is None:
            return self._fail(
                f"quote must be a boolean-like value, got {invocation.arguments.get('quote')!r}",
                {"quote": str(invocation.arguments.get("quote"))},
            )

        transformed = html.escape(document, quote=quote) if mode == "encode" else html.unescape(document)

        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=transformed,
            metadata={
                "mode": mode,
                "quote": quote,
                "chars": len(transformed),
            },
        )

    @staticmethod
    def _parse_bool(value: object) -> bool | None:
        """Coerce a boolean-like argument."""

        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "1", "yes", "on"}:
                return True
            if lowered in {"false", "0", "no", "off"}:
                return False
        return None

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
