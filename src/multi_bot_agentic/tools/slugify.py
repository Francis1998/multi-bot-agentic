"""Deterministic slugify tool.

Agent runs frequently need a stable, URL- and filesystem-safe token derived from
free-form text: a branch or path segment, a cache-file name, an anchor id, or a
human-readable key for an observation. Producing that token by hand is
error-prone (accents, punctuation, and whitespace all need normalising), and a
language model cannot be trusted to do it consistently. This tool converts text
into an ASCII slug deterministically: it strips diacritics, lowercases, replaces
every run of non-alphanumeric characters with a single separator, and trims
leading/trailing separators. It never executes code and never makes a network
request, and returns a structured failure for empty or oversized input, an
unusable separator, or text that reduces to an empty slug — matching the
``hash``, ``base64``, ``json_format``, ``url_parse``, and ``uuid5`` tool
contracts.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 8_000
_DEFAULT_SEPARATOR: Final[str] = "-"
_MAX_SEPARATOR_CHARS: Final[int] = 8
# A separator must itself be slug-safe so the output stays URL/filesystem clean;
# only ASCII alphanumerics plus the two conventional word separators are allowed.
_SEPARATOR_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9_-]{1,8}$")
_NON_ALPHANUMERIC: Final[re.Pattern[str]] = re.compile(r"[^a-z0-9]+")


class SlugifyTool:
    """Convert arbitrary text into a deterministic ASCII slug."""

    name = "slugify"
    description = "Converts text into a URL-safe ASCII slug (separator default '-', optional max_length)."

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Slugify the invocation text.

        Args:
            invocation: Tool invocation whose ``text`` argument holds the text to
                slugify, whose optional ``separator`` argument overrides the
                default ``-`` word separator, and whose optional ``max_length``
                argument caps the slug length (truncated on a separator
                boundary so no partial word or trailing separator remains).

        Returns:
            Tool result whose ``content`` is the slug, or ``ok=False`` and an
            explanation when the text is empty or too long, the separator is
            unusable, ``max_length`` is not a positive integer, or the text
            reduces to an empty slug.
        """

        document = str(invocation.arguments.get("text", ""))
        if not document.strip():
            return self._fail("text is empty", {})
        if len(document) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"text exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(document)},
            )

        separator = str(invocation.arguments.get("separator", _DEFAULT_SEPARATOR))
        if not _SEPARATOR_PATTERN.match(separator):
            return self._fail(
                f"unusable separator: {separator!r}; must match [A-Za-z0-9_-]{{1,{_MAX_SEPARATOR_CHARS}}}",
                {"separator": separator},
            )

        max_length = invocation.arguments.get("max_length")
        parsed_max_length = self._parse_max_length(max_length)
        if max_length is not None and parsed_max_length is None:
            return self._fail(
                f"max_length must be a positive integer, got {max_length!r}",
                {"max_length": str(max_length)},
            )

        slug = self._slugify(document, separator)
        if parsed_max_length is not None:
            slug = self._truncate(slug, separator, parsed_max_length)
        if not slug:
            return self._fail("text reduces to an empty slug", {})

        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=slug,
            metadata={"separator": separator, "length": len(slug)},
        )

    @staticmethod
    def _slugify(document: str, separator: str) -> str:
        """Normalise text into an ASCII slug joined by ``separator``.

        Args:
            document: Raw input text.
            separator: Word separator to join alphanumeric runs.

        Returns:
            The slug with diacritics stripped, lowercased, non-alphanumeric runs
            collapsed to ``separator``, and leading/trailing separators trimmed.
        """

        decomposed = unicodedata.normalize("NFKD", document)
        ascii_text = decomposed.encode("ascii", "ignore").decode("ascii").lower()
        collapsed = _NON_ALPHANUMERIC.sub(separator, ascii_text)
        return collapsed.strip(separator)

    @staticmethod
    def _truncate(slug: str, separator: str, max_length: int) -> str:
        """Truncate a slug to ``max_length`` on a separator boundary.

        Args:
            slug: The full slug.
            separator: Word separator used within the slug.
            max_length: Maximum allowed slug length.

        Returns:
            The slug truncated to at most ``max_length`` characters, keeping only
            whole words so no partial word or trailing separator remains (unless
            the first word alone already exceeds ``max_length``, in which case
            that word is hard-cut).
        """

        if len(slug) <= max_length:
            return slug
        words = slug.split(separator)
        kept = ""
        for word in words:
            candidate = word if not kept else f"{kept}{separator}{word}"
            if len(candidate) > max_length:
                break
            kept = candidate
        if kept:
            return kept
        return words[0][:max_length]

    @staticmethod
    def _parse_max_length(value: object) -> int | None:
        """Coerce a ``max_length`` argument to a positive integer.

        Args:
            value: Raw ``max_length`` argument (may be absent, int, or string).

        Returns:
            The positive integer value, or None when absent or invalid.
        """

        if value is None or isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value if value > 0 else None
        if isinstance(value, str):
            text = value.strip()
            if text.isdigit() and int(text) > 0:
                return int(text)
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
