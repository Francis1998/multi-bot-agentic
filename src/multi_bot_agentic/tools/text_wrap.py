"""Deterministic text wrapping tool.

Agent runs routinely need to reflow long lines for logs, rationales, or
bounded previews before the next LLM turn. Asking a language model to wrap text
is unreliable (ragged widths, dropped newlines, inconsistent indentation). This
tool wraps or fills lines via stdlib :mod:`textwrap` with a configurable width
and ``wrap`` or ``fill`` mode. It never executes code and never makes network
requests. Safe for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.
"""

from __future__ import annotations

import textwrap
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_DEFAULT_WIDTH: Final[int] = 80
_MIN_WIDTH: Final[int] = 1
_MAX_WIDTH: Final[int] = 500
_DEFAULT_MODE: Final[str] = "wrap"
_ALLOWED_MODES: Final[frozenset[str]] = frozenset({"wrap", "fill"})


class TextWrapTool:
    """Wrap or fill text to a maximum line width."""

    name = "text_wrap"
    description = "Wraps or fills text via textwrap (width default 80, mode wrap|fill); max 20_000 chars."

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Wrap or fill the invocation text.

        Args:
            invocation: Tool invocation whose ``text`` argument holds the
                document, whose optional ``width`` argument sets the maximum
                line width (default 80), and whose optional ``mode`` argument
                selects ``wrap`` (default) or ``fill``.

        Returns:
            Tool result whose ``content`` is the wrapped text and whose metadata
            reports ``width``, ``mode``, and ``lines``, or ``ok=False`` when the
            document is empty, too large, or arguments are invalid.
        """

        document = str(invocation.arguments.get("text", ""))
        if not document:
            return self._fail("text is empty", {})
        if len(document) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"text exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(document)},
            )

        width = self._parse_width(invocation.arguments.get("width", _DEFAULT_WIDTH))
        if width is None:
            return self._fail(
                f"width must be an integer {_MIN_WIDTH}..{_MAX_WIDTH}, got {invocation.arguments.get('width')!r}",
                {"width": str(invocation.arguments.get("width"))},
            )

        mode = str(invocation.arguments.get("mode", _DEFAULT_MODE)).strip().lower()
        if mode not in _ALLOWED_MODES:
            return self._fail(
                f"unsupported mode: {mode!r}; must be wrap or fill",
                {"mode": mode},
            )

        if mode == "fill":
            wrapped = textwrap.fill(document, width=width)
        else:
            wrapped = "\n".join(textwrap.wrap(document, width=width))

        line_count = 0 if not wrapped else len(wrapped.splitlines())
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=wrapped,
            metadata={
                "width": width,
                "mode": mode,
                "lines": line_count,
                "chars": len(wrapped),
            },
        )

    @staticmethod
    def _parse_width(value: object) -> int | None:
        """Coerce a width argument to an allowed positive integer."""

        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value if _MIN_WIDTH <= value <= _MAX_WIDTH else None
        if isinstance(value, str):
            text = value.strip()
            if text.isdigit():
                parsed = int(text)
                return parsed if _MIN_WIDTH <= parsed <= _MAX_WIDTH else None
        return None

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
