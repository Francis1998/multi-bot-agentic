"""Deterministic bounded per-line title-casing tool.

Agents often need display titles for every heading or record in a document while
retaining its line structure. This tool title-cases each line independently,
optionally lowercases first for consistent capitalization, preserves line
endings, and never executes code or makes network requests. It is safe for
GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.

Arguments may be supplied separately or in one ``text`` value split on
``<<<TEXT_TITLE_LINES>>>`` with a ``skip_empty:lowercase_first`` suffix.
"""

from __future__ import annotations

from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_DEFAULT_SKIP_EMPTY: Final[bool] = True
_DEFAULT_LOWERCASE_FIRST: Final[bool] = False
_SPLIT_SENTINEL: Final[str] = "<<<TEXT_TITLE_LINES>>>"
_TRUTHY: Final[frozenset[str]] = frozenset({"1", "true", "yes", "on"})
_FALSY: Final[frozenset[str]] = frozenset({"0", "false", "no", "off"})


class TextTitleLinesTool:
    """Title-case every document line while preserving endings."""

    name = "text_title_lines"
    description = (
        "Title-cases each line independently while preserving line endings "
        "(skip_empty true and lowercase_first false by default); accepts "
        "text+options or <<<TEXT_TITLE_LINES>>>; max 20_000 chars."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Title-case each line using bounded stdlib string operations."""

        document, skip_empty, lowercase_first, resolve_error = self._resolve_arguments(invocation.arguments)
        if resolve_error is not None:
            return self._fail(resolve_error, {})
        assert document is not None and skip_empty is not None and lowercase_first is not None

        if not document.strip():
            return self._fail("text is empty", {})
        if len(document) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"text exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(document)},
            )

        lines = document.splitlines(keepends=True)
        output_parts: list[str] = []
        titled_lines = 0
        skipped_empty_lines = 0
        output_chars = 0
        for line in lines:
            body, ending = self._split_line_ending(line)
            if skip_empty and not body.strip():
                titled = body
                skipped_empty_lines += 1
            else:
                titled = self._title_line(body, lowercase_first)
                titled_lines += 1

            output_line = f"{titled}{ending}"
            output_chars += len(output_line)
            if output_chars > _MAX_DOCUMENT_CHARS:
                return self._fail(
                    f"title-cased output exceeds max_chars={_MAX_DOCUMENT_CHARS}",
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
                "lowercase_first": lowercase_first,
                "skip_empty": skip_empty,
                "skipped_empty_lines": skipped_empty_lines,
                "titled_lines": titled_lines,
            },
        )

    @classmethod
    def _resolve_arguments(
        cls,
        arguments: dict[str, object],
    ) -> tuple[str | None, bool | None, bool | None, str | None]:
        """Resolve text and options from explicit arguments or sentinel syntax."""

        text = str(arguments.get("text", ""))
        has_options = any(key in arguments for key in ("skip_empty", "lowercase_first"))
        if has_options:
            skip_empty = cls._parse_bool(arguments.get("skip_empty", _DEFAULT_SKIP_EMPTY))
            if skip_empty is None:
                return None, None, None, f"skip_empty must be a boolean, got {arguments['skip_empty']!r}"

            lowercase_first = cls._parse_bool(arguments.get("lowercase_first", _DEFAULT_LOWERCASE_FIRST))
            if lowercase_first is None:
                return (
                    None,
                    None,
                    None,
                    f"lowercase_first must be a boolean, got {arguments['lowercase_first']!r}",
                )
            return text, skip_empty, lowercase_first, None

        if _SPLIT_SENTINEL not in text:
            return text, _DEFAULT_SKIP_EMPTY, _DEFAULT_LOWERCASE_FIRST, None

        document, suffix = text.split(_SPLIT_SENTINEL, maxsplit=1)
        if _SPLIT_SENTINEL in suffix:
            return None, None, None, "text contains more than one <<<TEXT_TITLE_LINES>>> sentinel"
        return cls._parse_sentinel(document, suffix)

    @classmethod
    def _parse_sentinel(
        cls,
        document: str,
        suffix: str,
    ) -> tuple[str | None, bool | None, bool | None, str | None]:
        """Parse ``skip_empty[:lowercase_first]`` sentinel options."""

        stripped = suffix.strip()
        if not stripped:
            return document, _DEFAULT_SKIP_EMPTY, _DEFAULT_LOWERCASE_FIRST, None
        parts = [part.strip() for part in stripped.split(":")]
        if not 1 <= len(parts) <= 2:
            return None, None, None, "sentinel suffix must be skip_empty[:lowercase_first]"

        skip_empty = cls._parse_bool(parts[0])
        if skip_empty is None:
            return None, None, None, f"skip_empty must be a boolean, got {parts[0]!r}"

        lowercase_first = _DEFAULT_LOWERCASE_FIRST
        if len(parts) == 2:
            parsed_lowercase_first = cls._parse_bool(parts[1])
            if parsed_lowercase_first is None:
                return None, None, None, f"lowercase_first must be a boolean, got {parts[1]!r}"
            lowercase_first = parsed_lowercase_first
        return document, skip_empty, lowercase_first, None

    @staticmethod
    def _title_line(body: str, lowercase_first: bool) -> str:
        """Title-case one line body, optionally lowercasing first."""

        value = body.lower() if lowercase_first else body
        return value.title()

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

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
