"""Orchestration-layer truncation for oversized tool result strings.

Caps tool observation text before it is fed back into the LLM context.
Distinct from the user-facing ``truncate`` tool in ``tools/text_truncate.py`` —
this is a thin, stdlib-only guard for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x /
Kimi K2 agent loops. Fills a gap vs AutoGen/CrewAI/LangGraph, which often
leave raw tool payloads unbounded.
"""

from __future__ import annotations

from dataclasses import dataclass

_DEFAULT_MARKER = "…[truncated]…"


@dataclass(frozen=True)
class TruncatedToolResult:
    """Outcome of truncating a tool result string.

    Attributes:
        original_len: Character length of the input before truncation.
        truncated_len: Character length of the returned ``text``.
        text: Possibly truncated content (never empty when input is non-empty
            and ``max_chars >= 1``).
        was_truncated: Whether any characters were removed.
        marker: Ellipsis marker embedded when truncated (empty when not).
    """

    original_len: int
    truncated_len: int
    text: str
    was_truncated: bool
    marker: str


class ToolResultTruncator:
    """Soft mid-string truncator for tool result payloads.

    Caller-driven v1: wrap tool result content before observe / prompt assembly.
    Does not wire into ``AgentRunner`` automatically.

    Args:
        marker: Mid-string ellipsis marker inserted when truncating.
    """

    def __init__(self, *, marker: str = _DEFAULT_MARKER) -> None:
        if not isinstance(marker, str):
            raise TypeError("marker must be a str")
        if not marker:
            raise ValueError("marker must be non-empty")
        self._marker = marker

    def truncate(self, text: str, *, max_chars: int) -> TruncatedToolResult:
        """Truncate ``text`` to at most ``max_chars`` characters.

        Soft mid-string strategy: keep a head and a tail with ``marker`` in
        between when the input exceeds the budget. Guarantees a non-empty
        result when ``text`` is non-empty and ``max_chars >= 1``.

        Args:
            text: Tool result string to bound.
            max_chars: Maximum characters in the returned ``text`` (must be >= 0).

        Returns:
            TruncatedToolResult with lengths, text, and truncation metadata.

        Raises:
            TypeError: When ``text`` is not a string.
            ValueError: When ``max_chars`` is negative.
        """

        if not isinstance(text, str):
            raise TypeError("text must be a str")
        if max_chars < 0:
            raise ValueError("max_chars must be >= 0")

        original_len = len(text)
        if max_chars == 0:
            return TruncatedToolResult(
                original_len=original_len,
                truncated_len=0,
                text="",
                was_truncated=original_len > 0,
                marker=self._marker if original_len > 0 else "",
            )
        if original_len <= max_chars:
            return TruncatedToolResult(
                original_len=original_len,
                truncated_len=original_len,
                text=text,
                was_truncated=False,
                marker="",
            )

        marker = self._marker
        if len(marker) >= max_chars:
            # Budget too small for a full marker: keep a non-empty head slice.
            out = text[:max_chars]
            return TruncatedToolResult(
                original_len=original_len,
                truncated_len=len(out),
                text=out,
                was_truncated=True,
                marker=marker,
            )

        remaining = max_chars - len(marker)
        head = remaining // 2
        tail = remaining - head
        out = text[:head] + marker + text[-tail:] if tail else text[:head] + marker
        # Defensive: never return empty when input is non-empty and budget >= 1.
        if not out and text:
            out = text[:1]
        return TruncatedToolResult(
            original_len=original_len,
            truncated_len=len(out),
            text=out,
            was_truncated=True,
            marker=marker,
        )
