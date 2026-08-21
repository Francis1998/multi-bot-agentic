"""Deterministic bounded per-line slugification tool.

Agents often need stable slugs for every heading or record in a document while
retaining its line structure. This tool normalizes each line independently,
preserves line endings, and never executes code or makes network requests. It
is safe for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.

Arguments may be supplied separately or in one ``text`` value split on
``<<<TEXT_SLUG_LINES>>>`` with a ``separator:lowercase:skip_empty`` suffix.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_DEFAULT_SEPARATOR: Final[str] = "-"
_MAX_SEPARATOR_CHARS: Final[int] = 8
_DEFAULT_LOWERCASE: Final[bool] = True
_DEFAULT_SKIP_EMPTY: Final[bool] = True
_SPLIT_SENTINEL: Final[str] = "<<<TEXT_SLUG_LINES>>>"
_SEPARATOR_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9_-]{1,8}$")
_NON_ALPHANUMERIC: Final[re.Pattern[str]] = re.compile(r"[^A-Za-z0-9]+")
_TRUTHY: Final[frozenset[str]] = frozenset({"1", "true", "yes", "on"})
_FALSY: Final[frozenset[str]] = frozenset({"0", "false", "no", "off"})


class TextSlugLinesTool:
    """Convert every document line into a deterministic ASCII slug."""

    name = "text_slug_lines"
    description = (
        "Slugifies each line independently while preserving line endings "
        "(separator '-' and lowercase/skip_empty true by default); accepts "
        "text+options or <<<TEXT_SLUG_LINES>>>; max 20_000 chars."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Slugify each line using bounded stdlib string operations."""

        document, separator, lowercase, skip_empty, resolve_error = self._resolve_arguments(invocation.arguments)
        if resolve_error is not None:
            return self._fail(resolve_error, {})
        assert document is not None and separator is not None and lowercase is not None and skip_empty is not None

        if not document.strip():
            return self._fail("text is empty", {})
        if len(document) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"text exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(document)},
            )

        lines = document.splitlines(keepends=True)
        output_parts: list[str] = []
        slugged_lines = 0
        skipped_empty_lines = 0
        output_chars = 0
        for line in lines:
            body, ending = self._split_line_ending(line)
            if skip_empty and not body.strip():
                slugged = body
                skipped_empty_lines += 1
            else:
                slugged = self._slugify_line(body, separator, lowercase)
                slugged_lines += 1

            output_line = f"{slugged}{ending}"
            output_chars += len(output_line)
            if output_chars > _MAX_DOCUMENT_CHARS:
                return self._fail(
                    f"slugified output exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                    {"chars": output_chars, "input_chars": len(document)},
                )
            output_parts.append(output_line)

        content = "".join(output_parts)
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=content,
            metadata={
                "chars": len(content),
                "input_chars": len(document),
                "lines": len(lines),
                "lowercase": lowercase,
                "separator": separator,
                "skip_empty": skip_empty,
                "skipped_empty_lines": skipped_empty_lines,
                "slugged_lines": slugged_lines,
            },
        )

    @classmethod
    def _resolve_arguments(
        cls,
        arguments: dict[str, object],
    ) -> tuple[str | None, str | None, bool | None, bool | None, str | None]:
        """Resolve text and options from explicit arguments or sentinel syntax."""

        text = str(arguments.get("text", ""))
        has_options = any(key in arguments for key in ("separator", "lowercase", "skip_empty"))
        if has_options:
            separator = str(arguments.get("separator", _DEFAULT_SEPARATOR))
            if not _SEPARATOR_PATTERN.fullmatch(separator):
                return None, None, None, None, cls._separator_error(separator)

            lowercase = cls._parse_bool(arguments.get("lowercase", _DEFAULT_LOWERCASE))
            if lowercase is None:
                return None, None, None, None, f"lowercase must be a boolean, got {arguments['lowercase']!r}"

            skip_empty = cls._parse_bool(arguments.get("skip_empty", _DEFAULT_SKIP_EMPTY))
            if skip_empty is None:
                return None, None, None, None, f"skip_empty must be a boolean, got {arguments['skip_empty']!r}"
            return text, separator, lowercase, skip_empty, None

        if _SPLIT_SENTINEL not in text:
            return text, _DEFAULT_SEPARATOR, _DEFAULT_LOWERCASE, _DEFAULT_SKIP_EMPTY, None

        document, suffix = text.split(_SPLIT_SENTINEL, maxsplit=1)
        if _SPLIT_SENTINEL in suffix:
            return None, None, None, None, "text contains more than one <<<TEXT_SLUG_LINES>>> sentinel"
        return cls._parse_sentinel(document, suffix)

    @classmethod
    def _parse_sentinel(
        cls,
        document: str,
        suffix: str,
    ) -> tuple[str | None, str | None, bool | None, bool | None, str | None]:
        """Parse ``separator[:lowercase[:skip_empty]]`` sentinel options."""

        stripped = suffix.strip()
        if not stripped:
            return document, _DEFAULT_SEPARATOR, _DEFAULT_LOWERCASE, _DEFAULT_SKIP_EMPTY, None
        parts = [part.strip() for part in stripped.split(":")]
        if not 1 <= len(parts) <= 3:
            return None, None, None, None, "sentinel suffix must be separator[:lowercase[:skip_empty]]"

        separator = parts[0]
        if not _SEPARATOR_PATTERN.fullmatch(separator):
            return None, None, None, None, cls._separator_error(separator)

        lowercase = _DEFAULT_LOWERCASE
        if len(parts) >= 2:
            parsed_lowercase = cls._parse_bool(parts[1])
            if parsed_lowercase is None:
                return None, None, None, None, f"lowercase must be a boolean, got {parts[1]!r}"
            lowercase = parsed_lowercase

        skip_empty = _DEFAULT_SKIP_EMPTY
        if len(parts) == 3:
            parsed_skip_empty = cls._parse_bool(parts[2])
            if parsed_skip_empty is None:
                return None, None, None, None, f"skip_empty must be a boolean, got {parts[2]!r}"
            skip_empty = parsed_skip_empty
        return document, separator, lowercase, skip_empty, None

    @staticmethod
    def _slugify_line(body: str, separator: str, lowercase: bool) -> str:
        """Normalize one line to ASCII and join alphanumeric runs."""

        decomposed = unicodedata.normalize("NFKD", body)
        ascii_text = decomposed.encode("ascii", "ignore").decode("ascii")
        if lowercase:
            ascii_text = ascii_text.lower()
        words = [word for word in _NON_ALPHANUMERIC.split(ascii_text) if word]
        return separator.join(words)

    @staticmethod
    def _split_line_ending(line: str) -> tuple[str, str]:
        """Separate a line body from its original line ending."""

        if line.endswith("\r\n"):
            return line[:-2], "\r\n"
        if line.endswith("\n") or line.endswith("\r"):
            return line[:-1], line[-1]
        return line, ""

    @staticmethod
    def _parse_bool(value: object) -> bool | None:
        """Coerce a boolean-like option."""

        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in _TRUTHY:
                return True
            if normalized in _FALSY:
                return False
        return None

    @staticmethod
    def _separator_error(separator: str) -> str:
        """Describe the bounded separator contract."""

        return f"unusable separator: {separator!r}; must match [A-Za-z0-9_-]{{1,{_MAX_SEPARATOR_CHARS}}}"

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
