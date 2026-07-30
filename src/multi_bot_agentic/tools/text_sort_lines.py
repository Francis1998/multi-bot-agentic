"""Deterministic line-sorting tool.

Agent runs often need a stable ordering of multi-line observations: deduplicating
checklist items, normalizing a bag of tags, or comparing two line-oriented
payloads after sorting. Asking a language model to sort is unreliable (dropped
lines, unstable ties, invented uniqueness). This tool sorts the lines of the
invocation text ascending or descending, optionally unique-ifying them, with
bounded input size and structured failures for empty or oversized input or an
unsupported order. It never executes code and never makes a network request,
matching the ``diff``, ``truncate``, ``hash``, and ``slugify`` tool contracts.
"""

from __future__ import annotations

from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_DEFAULT_ORDER: Final[str] = "asc"
_ORDERS: Final[frozenset[str]] = frozenset({"asc", "desc", "ascending", "descending"})
_TRUTHY: Final[frozenset[str]] = frozenset({"1", "true", "yes", "on"})
_FALSY: Final[frozenset[str]] = frozenset({"0", "false", "no", "off"})


class TextSortLinesTool:
    """Sort the lines of a text document ascending or descending."""

    name = "text_sort_lines"
    description = "Sorts text lines ascending/descending (order default asc; optional unique)."

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Sort the lines of the document in the invocation text.

        Args:
            invocation: Tool invocation whose ``text`` argument holds the
                document to sort, whose optional ``order`` argument selects
                ascending (``asc`` / ``ascending``) or descending (``desc`` /
                ``descending``; default ``asc``), and whose optional ``unique``
                argument drops duplicate lines after sorting.

        Returns:
            Tool result whose ``content`` is the sorted lines joined by
            newlines, or ``ok=False`` and an explanation when the document is
            empty/oversized, ``order`` is unsupported, or ``unique`` is not
            boolean-like.
        """

        document = str(invocation.arguments.get("text", ""))
        if not document:
            return self._fail("text is empty", {})
        if len(document) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"text exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(document)},
            )

        order_raw = str(invocation.arguments.get("order", _DEFAULT_ORDER)).strip().lower()
        if order_raw not in _ORDERS:
            supported = ", ".join(sorted(_ORDERS))
            return self._fail(
                f"unsupported order: {order_raw!r}; supported: {supported}",
                {"order": order_raw},
            )
        descending = order_raw in {"desc", "descending"}
        order = "desc" if descending else "asc"

        if "unique" in invocation.arguments:
            unique = self._parse_bool(invocation.arguments.get("unique"))
            if unique is None:
                return self._fail(
                    f"unique must be a boolean, got {invocation.arguments.get('unique')!r}",
                    {"unique": str(invocation.arguments.get("unique"))},
                )
        else:
            unique = False

        lines = document.splitlines()
        original_line_count = len(lines)
        sorted_lines = sorted(lines, reverse=descending)
        if unique:
            # Preserve first-seen order of the already-sorted sequence so
            # uniqueness is consecutive after sort (like ``sort -u``).
            sorted_lines = list(dict.fromkeys(sorted_lines))

        return ToolResult(
            tool_name=self.name,
            ok=True,
            content="\n".join(sorted_lines),
            metadata={
                "order": order,
                "unique": unique,
                "lines": len(sorted_lines),
                "original_lines": original_line_count,
                "chars": len(document),
            },
        )

    @staticmethod
    def _parse_bool(value: object) -> bool | None:
        """Coerce a boolean-like ``unique`` argument to a bool.

        Args:
            value: Raw argument value.

        Returns:
            The boolean value, or None when not boolean-like.
        """

        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            text = value.strip().lower()
            if text in _TRUTHY:
                return True
            if text in _FALSY:
                return False
        return None

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result.

        Args:
            message: Human-readable failure explanation.
            metadata: Structured metadata for the failure.

        Returns:
            A ``ok=False`` tool result carrying the message and metadata.
        """

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
