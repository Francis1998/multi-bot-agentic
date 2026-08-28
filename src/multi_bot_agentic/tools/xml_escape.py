"""XML special-character escape/unescape tool.

Agents often need to escape ``&``, ``<``, and ``>`` before embedding text in
XML handoff snippets, or unescape entities after scraping. Asking a language
model to escape XML is unreliable (missed ampersands, double-escaping). This
tool uses stdlib :func:`xml.sax.saxutils.escape` / :func:`xml.sax.saxutils.unescape`.
It never executes code and never makes network requests. Safe for GPT-5.5 /
Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.
"""

from __future__ import annotations

from typing import Final
from xml.sax.saxutils import escape, unescape

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_DEFAULT_MODE: Final[str] = "escape"
_ALLOWED_MODES: Final[frozenset[str]] = frozenset({"escape", "unescape"})


class XmlEscapeTool:
    """Escape or unescape XML special characters."""

    name = "xml_escape"
    description = (
        "Escapes or unescapes XML special chars via xml.sax.saxutils (mode escape|unescape); max 20_000 chars."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Escape or unescape XML special characters in the invocation text.

        Args:
            invocation: Tool invocation whose ``text`` argument holds the
                document and whose optional ``mode`` argument selects
                ``escape`` (default) or ``unescape``.

        Returns:
            Tool result whose ``content`` is the transformed text and whose
            metadata reports ``mode`` and ``chars``, or ``ok=False`` when the
            document is empty, too large, or ``mode`` is unsupported.
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
            supported = ", ".join(sorted(_ALLOWED_MODES))
            return self._fail(
                f"unsupported mode: {mode!r}; supported: {supported}",
                {"mode": mode},
            )

        transformed = escape(document) if mode == "escape" else unescape(document)
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=transformed,
            metadata={
                "mode": mode,
                "chars": len(transformed),
                "input_chars": len(document),
            },
        )

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
