"""Deterministic Markdown table-of-contents generator.

Documentation agents (LlamaIndex / MkDocs-style workflows) often need a TOC
from ATX headings without calling an LLM. This tool extracts ``#``..``######``
headings, emits a nested bullet list with slug anchors, and never executes
code or makes network requests. Safe for GPT-5.5 / Claude Sonnet 4.6 /
Gemini 3.x / Kimi K2 workers.

Arguments may be supplied separately or in one ``text`` value split on
``<<<MARKDOWN_TOC>>>`` with a ``max_level`` suffix (default 3, range 1..6).
"""

from __future__ import annotations

import re
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_DEFAULT_MAX_LEVEL: Final[int] = 3
_MIN_LEVEL: Final[int] = 1
_MAX_LEVEL: Final[int] = 6
_SPLIT_SENTINEL: Final[str] = "<<<MARKDOWN_TOC>>>"
_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_NON_SLUG = re.compile(r"[^a-z0-9\s-]")
_SPACES = re.compile(r"\s+")


class MarkdownTocTool:
    """Build a Markdown TOC from ATX headings."""

    name = "markdown_toc"
    description = (
        "Builds a nested Markdown TOC from ATX headings (#..######) up to "
        "max_level (default 3); accepts <<<MARKDOWN_TOC>>>; max 20_000 chars."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Generate a TOC from the invocation Markdown text."""

        document, max_level, resolve_error = self._resolve_arguments(invocation.arguments)
        if resolve_error is not None:
            return self._fail(resolve_error, {})
        assert document is not None and max_level is not None

        if not document.strip():
            return self._fail("text is empty", {})
        if len(document) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"text exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(document)},
            )

        headings: list[tuple[int, str, str]] = []
        for line in document.splitlines():
            match = _HEADING.match(line)
            if match is None:
                continue
            level = len(match.group(1))
            if level > max_level:
                continue
            title = match.group(2).strip()
            if not title:
                continue
            headings.append((level, title, self._slugify(title)))

        if not headings:
            return self._fail("no ATX headings found", {"max_level": max_level})

        min_level = min(level for level, _title, _slug in headings)
        lines: list[str] = []
        for level, title, slug in headings:
            indent = "  " * (level - min_level)
            lines.append(f"{indent}- [{title}](#{slug})")
        content = "\n".join(lines) + "\n"
        if len(content) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"toc output exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(content), "input_chars": len(document)},
            )
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=content,
            metadata={
                "chars": len(content),
                "input_chars": len(document),
                "headings": len(headings),
                "max_level": max_level,
            },
        )

    @classmethod
    def _resolve_arguments(cls, arguments: dict[str, object]) -> tuple[str | None, int | None, str | None]:
        """Resolve text and max_level from explicit args or sentinel syntax."""

        text = str(arguments.get("text", ""))
        if "max_level" in arguments:
            max_level = cls._parse_max_level(arguments.get("max_level"))
            if max_level is None:
                return (
                    None,
                    None,
                    (f"max_level must be an integer {_MIN_LEVEL}..{_MAX_LEVEL}, got {arguments.get('max_level')!r}"),
                )
            return text, max_level, None

        if _SPLIT_SENTINEL not in text:
            return text, _DEFAULT_MAX_LEVEL, None

        document, suffix = text.split(_SPLIT_SENTINEL, maxsplit=1)
        if _SPLIT_SENTINEL in suffix:
            return None, None, "text contains more than one <<<MARKDOWN_TOC>>> sentinel"
        stripped = suffix.strip()
        if not stripped:
            return document, _DEFAULT_MAX_LEVEL, None
        max_level = cls._parse_max_level(stripped)
        if max_level is None:
            return (
                None,
                None,
                f"max_level must be an integer {_MIN_LEVEL}..{_MAX_LEVEL}, got {stripped!r}",
            )
        return document, max_level, None

    @staticmethod
    def _parse_max_level(value: object) -> int | None:
        """Parse a bounded max_level integer."""

        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            parsed = value
        elif isinstance(value, str) and value.strip().isdigit():
            parsed = int(value.strip())
        else:
            return None
        if not _MIN_LEVEL <= parsed <= _MAX_LEVEL:
            return None
        return parsed

    @staticmethod
    def _slugify(title: str) -> str:
        """Build a GitHub-like heading slug."""

        lowered = title.lower()
        cleaned = _NON_SLUG.sub("", lowered)
        return _SPACES.sub("-", cleaned).strip("-") or "section"

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
