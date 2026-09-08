"""Deterministic conversation summarizer for multi-bot loops.

Compresses observation/message lists into a bounded rolling summary so long
runs stay within prompt budgets. Thinner than LangChain ConversationSummaryMemory
or CrewAI memory backends: no embeddings, no LLM call required for v1 — extractive
head/tail + keyword bullets suitable for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x /
Kimi K2 agent loops.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_/-]{2,}")
_STOP = frozenset(
    {
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "from",
        "have",
        "been",
        "were",
        "are",
        "was",
        "you",
        "your",
        "our",
        "their",
        "into",
        "about",
        "will",
        "can",
        "should",
        "would",
        "could",
        "a",
        "an",
        "of",
        "to",
        "in",
        "on",
        "at",
        "by",
        "or",
        "as",
        "is",
        "it",
        "be",
    }
)


@dataclass(frozen=True)
class ConversationSummary:
    """Rolling summary of a conversation transcript.

    Attributes:
        summary_text: Human-readable compressed summary.
        message_count: Number of source messages summarized.
        kept_head: Leading messages retained verbatim.
        kept_tail: Trailing messages retained verbatim.
        keywords: High-signal tokens extracted from the middle.
    """

    summary_text: str
    message_count: int
    kept_head: tuple[str, ...]
    kept_tail: tuple[str, ...]
    keywords: tuple[str, ...]


class ConversationSummarizer:
    """Extractive conversation summarizer with hard length caps.

    Args:
        max_summary_chars: Hard cap on ``summary_text`` length.
        keep_head: Number of leading messages to retain.
        keep_tail: Number of trailing messages to retain.
        max_keywords: Maximum keyword bullets from the middle.
    """

    def __init__(
        self,
        *,
        max_summary_chars: int = 1200,
        keep_head: int = 2,
        keep_tail: int = 2,
        max_keywords: int = 12,
    ) -> None:
        if max_summary_chars < 32:
            raise ValueError("max_summary_chars must be >= 32")
        if keep_head < 0 or keep_tail < 0:
            raise ValueError("keep_head and keep_tail must be >= 0")
        if max_keywords < 1:
            raise ValueError("max_keywords must be >= 1")
        self._max_summary_chars = max_summary_chars
        self._keep_head = keep_head
        self._keep_tail = keep_tail
        self._max_keywords = max_keywords

    def summarize(self, messages: list[str]) -> ConversationSummary:
        """Summarize a list of message strings.

        Args:
            messages: Ordered conversation / observation texts.

        Returns:
            ConversationSummary with head/tail retention and keyword bullets.

        Raises:
            ValueError: If any message is not a string.
        """

        if not isinstance(messages, list):
            raise TypeError("messages must be a list[str]")
        cleaned: list[str] = []
        for message in messages:
            if not isinstance(message, str):
                raise TypeError("messages must contain only strings")
            text = message.strip()
            if text:
                cleaned.append(text)

        if not cleaned:
            return ConversationSummary(
                summary_text="(empty conversation)",
                message_count=0,
                kept_head=(),
                kept_tail=(),
                keywords=(),
            )

        head_n = min(self._keep_head, len(cleaned))
        tail_n = min(self._keep_tail, max(0, len(cleaned) - head_n))
        head = tuple(cleaned[:head_n])
        tail = tuple(cleaned[-tail_n:]) if tail_n else ()
        middle_start = head_n
        middle_end = len(cleaned) - tail_n
        middle = cleaned[middle_start:middle_end] if middle_end > middle_start else []

        keywords = self._extract_keywords(middle)
        parts: list[str] = []
        if head:
            parts.append("HEAD:")
            parts.extend(f"- {item}" for item in head)
        if keywords:
            parts.append("KEYWORDS:")
            parts.append("- " + ", ".join(keywords))
        if middle and not keywords:
            parts.append(f"MIDDLE: {len(middle)} messages compressed")
        if tail:
            parts.append("TAIL:")
            parts.extend(f"- {item}" for item in tail)
        summary = "\n".join(parts)
        if len(summary) > self._max_summary_chars:
            summary = summary[: self._max_summary_chars - 3].rstrip() + "..."

        return ConversationSummary(
            summary_text=summary,
            message_count=len(cleaned),
            kept_head=head,
            kept_tail=tail,
            keywords=keywords,
        )

    def _extract_keywords(self, messages: list[str]) -> tuple[str, ...]:
        """Extract ranked keywords from middle messages."""

        counts: dict[str, int] = {}
        order: list[str] = []
        for message in messages:
            for match in _WORD_RE.findall(message):
                token = match.lower()
                if token in _STOP:
                    continue
                if token not in counts:
                    order.append(token)
                    counts[token] = 0
                counts[token] += 1
        ranked = sorted(order, key=lambda token: (-counts[token], order.index(token)))
        return tuple(ranked[: self._max_keywords])
