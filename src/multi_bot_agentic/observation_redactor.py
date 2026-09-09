"""Observation text redactor for multi-bot event logs.

Scrubs emails, phones, SSN-like numbers, and API-style tokens from observation
text before it is persisted or replayed. Distinct from AutoGen/CrewAI event
logs that often store raw transcripts verbatim — this is a thin, stdlib-only
guard suitable for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 loops.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

# Ordered so more specific patterns run before permissive ones: emails before
# phones, SSNs before phones, Bearer/sk tokens before generic digit runs.
_PATTERNS: Final[tuple[tuple[str, str, re.Pattern[str]], ...]] = (
    (
        "email",
        "[EMAIL]",
        re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"),
    ),
    (
        "token",
        "[TOKEN]",
        re.compile(
            r"(?:"
            r"Bearer\s+[A-Za-z0-9\-._~+/]+=*"
            r"|sk-[A-Za-z0-9]{16,}"
            r")"
        ),
    ),
    (
        "ssn",
        "[SSN]",
        re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    ),
    (
        "phone",
        "[PHONE]",
        re.compile(r"(?<!\w)(?:\+?\d{1,3}[.\s-]?)?(?:\(\d{3}\)|\d{3})[.\s-]?\d{3}[.\s-]?\d{4}(?!\w)"),
    ),
)


@dataclass(frozen=True)
class RedactionResult:
    """Outcome of redacting an observation string.

    Attributes:
        redacted_text: Text with sensitive spans replaced by placeholders.
        redaction_count: Total number of replacements performed.
        categories: Categories that had at least one match, in pattern order.
    """

    redacted_text: str
    redaction_count: int
    categories: tuple[str, ...]


class ObservationRedactor:
    """Redact emails, phones, SSN-like values, and API tokens from text.

    Caller-driven v1: wrap observation content before writing to the event log.
    """

    def redact(self, text: str) -> RedactionResult:
        """Redact sensitive patterns from ``text``.

        Args:
            text: Observation or log text to scrub.

        Returns:
            RedactionResult with redacted text, total count, and hit categories.

        Raises:
            TypeError: When ``text`` is not a string.
        """

        if not isinstance(text, str):
            raise TypeError("text must be a str")

        redacted = text
        total = 0
        hit: list[str] = []
        for category, placeholder, pattern in _PATTERNS:
            redacted, count = pattern.subn(placeholder, redacted)
            if count:
                total += count
                hit.append(category)
        return RedactionResult(
            redacted_text=redacted,
            redaction_count=total,
            categories=tuple(hit),
        )
