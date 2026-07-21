"""PII redaction tool.

Agent runs routinely relay free-form text between steps (model output, tool
results, user-supplied context) that may contain personal data. Persisting or
forwarding that text verbatim into the durable event log is a privacy and
compliance hazard. This tool scrubs common PII patterns (email addresses, phone
numbers, US Social Security numbers, IPv4 addresses, and IPv6 addresses) from a
document, replacing each match with a typed placeholder such as ``[EMAIL]``, and
reports how many values of each category were removed. It never executes code
and returns a structured failure for empty or oversized input, matching the
calculator and ``json_format`` tool contracts.
"""

from __future__ import annotations

import re
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000

# Ordered so that more specific patterns run before more permissive ones: an
# email is redacted before its digits can be misread as a phone number, and a
# Social Security number (3-2-4 digits) is redacted before the phone pattern.
# IPv6 runs before IPv4 so a mixed literal is not partially consumed as dotted
# quads; IPv4 still covers standalone dotted addresses.
_REDACTIONS: Final[tuple[tuple[str, str, re.Pattern[str]], ...]] = (
    (
        "email",
        "[EMAIL]",
        re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"),
    ),
    (
        "ssn",
        "[SSN]",
        re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    ),
    (
        "ipv6",
        "[IP]",
        # Covers compressed forms such as ``2001:db8::1`` and ``::1``, plus a
        # full eight-hextet form. Require at least one ``:`` so bare hex tokens
        # are not mangled. Word-ish boundaries avoid eating surrounding words.
        re.compile(
            r"(?<![\w:])(?:"
            r"(?:[0-9A-Fa-f]{1,4}:){7}[0-9A-Fa-f]{1,4}"
            r"|(?:[0-9A-Fa-f]{1,4}:){1,7}:"
            r"|:(?::[0-9A-Fa-f]{1,4}){1,7}"
            r"|(?:[0-9A-Fa-f]{1,4}:){1,6}:[0-9A-Fa-f]{1,4}"
            r"|(?:[0-9A-Fa-f]{1,4}:){1,5}(?::[0-9A-Fa-f]{1,4}){1,2}"
            r"|(?:[0-9A-Fa-f]{1,4}:){1,4}(?::[0-9A-Fa-f]{1,4}){1,3}"
            r"|(?:[0-9A-Fa-f]{1,4}:){1,3}(?::[0-9A-Fa-f]{1,4}){1,4}"
            r"|(?:[0-9A-Fa-f]{1,4}:){1,2}(?::[0-9A-Fa-f]{1,4}){1,5}"
            r"|[0-9A-Fa-f]{1,4}:(?::[0-9A-Fa-f]{1,4}){1,6}"
            r"|::"
            r")(?![\w:])"
        ),
    ),
    (
        "ipv4",
        "[IP]",
        # Each octet is bounded to 0-255 so genuine addresses are redacted while
        # unrelated dotted numbers (e.g. the build version ``300.400.500.600``)
        # are not mangled into ``[IP]``. A bare ``\d{1,3}`` matched any 0-999
        # group and over-redacted such values.
        re.compile(
            r"\b(?:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}"
            r"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\b"
        ),
    ),
    (
        "phone",
        "[PHONE]",
        # The number may begin with a parenthesised area code (``(415) 555-1234``).
        # A leading ``\b`` cannot match before ``(`` (a non-word character), which
        # left parenthesised numbers preceded by whitespace unredacted; use a
        # ``(?<!\w)``/``(?!\w)`` boundary that holds whether the number starts with
        # a digit or a ``(``.
        re.compile(r"(?<!\w)(?:\+?\d{1,3}[.\s-]?)?(?:\(\d{3}\)|\d{3})[.\s-]?\d{3}[.\s-]?\d{4}(?!\w)"),
    ),
)


class RedactionTool:
    """Redact common PII patterns from a text document."""

    name = "redact"
    description = "Redacts emails, phone numbers, SSNs, IPv4, and IPv6 addresses from text."

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Redact PII from the document in the invocation text.

        Args:
            invocation: Tool invocation whose ``text`` argument holds the
                document to scrub.

        Returns:
            Tool result with the redacted document and per-category counts, or
            ``ok=False`` and an explanation when the document is empty or too
            long.
        """

        document = str(invocation.arguments.get("text", ""))
        if not document.strip():
            return ToolResult(
                tool_name=self.name,
                ok=False,
                content="document is empty",
                metadata={},
            )
        if len(document) > _MAX_DOCUMENT_CHARS:
            return ToolResult(
                tool_name=self.name,
                ok=False,
                content=f"document exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                metadata={"chars": len(document)},
            )

        redacted = document
        counts: dict[str, int] = {}
        total = 0
        for category, placeholder, pattern in _REDACTIONS:
            redacted, count = pattern.subn(placeholder, redacted)
            counts[category] = count
            total += count

        counts["total"] = total
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=redacted,
            metadata=counts,
        )
