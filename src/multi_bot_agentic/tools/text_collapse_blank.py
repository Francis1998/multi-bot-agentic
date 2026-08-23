"""Deterministic blank-line collapsing tool.

Agents often need compact logs or rationales without long runs of empty lines.
This tool collapses consecutive blank or whitespace-only lines to at most
``max_blank`` blank lines (default 1), preserves non-blank line endings, and
never executes code or makes network requests. Safe for GPT-5.5 /
Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.

Arguments may be supplied separately or in one ``text`` value split on
``<<<TEXT_COLLAPSE_BLANK>>>`` with a ``max_blank`` suffix.
"""

from __future__ import annotations

from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_DEFAULT_MAX_BLANK: Final[int] = 1
_MIN_MAX_BLANK: Final[int] = 0
_MAX_MAX_BLANK: Final[int] = 100
_SPLIT_SENTINEL: Final[str] = "<<<TEXT_COLLAPSE_BLANK>>>"


class TextCollapseBlankTool:
    """Collapse runs of blank lines to a configured maximum."""

    name = "text_collapse_blank"
    description = (
        "Collapses consecutive blank/whitespace-only lines to at most "
        "max_blank blank lines (default 1); accepts <<<TEXT_COLLAPSE_BLANK>>>; "
        "max 20_000 chars."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Collapse blank-line runs in the invocation text."""

        document, max_blank, resolve_error = self._resolve_arguments(invocation.arguments)
        if resolve_error is not None:
            return self._fail(resolve_error, {})
        assert document is not None and max_blank is not None

        if not document.strip():
            return self._fail("text is empty", {})
        if len(document) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"text exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(document)},
            )

        lines = document.splitlines(keepends=True)
        output_parts: list[str] = []
        blank_run = 0
        collapsed_runs = 0
        kept_blank_lines = 0
        non_blank_lines = 0
        output_chars = 0

        for line in lines:
            body, ending = self._split_line_ending(line)
            is_blank = not body.strip()
            if is_blank:
                if blank_run >= max_blank:
                    collapsed_runs += 1
                    continue
                blank_run += 1
                kept_blank_lines += 1
                emitted = f"{body}{ending}"
            else:
                blank_run = 0
                non_blank_lines += 1
                emitted = f"{body}{ending}"

            output_chars += len(emitted)
            if output_chars > _MAX_DOCUMENT_CHARS:
                return self._fail(
                    f"collapsed output exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                    {"chars": output_chars, "input_chars": len(document)},
                )
            output_parts.append(emitted)

        content = "".join(output_parts)
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=content,
            metadata={
                "chars": len(content),
                "input_chars": len(document),
                "lines": len(lines),
                "max_blank": max_blank,
                "collapsed_runs": collapsed_runs,
                "kept_blank_lines": kept_blank_lines,
                "non_blank_lines": non_blank_lines,
            },
        )

    @classmethod
    def _resolve_arguments(cls, arguments: dict[str, object]) -> tuple[str | None, int | None, str | None]:
        """Resolve text and max_blank from explicit args or sentinel syntax."""

        text = str(arguments.get("text", ""))
        if "max_blank" in arguments:
            max_blank = cls._parse_max_blank(arguments.get("max_blank"))
            if max_blank is None:
                return (
                    None,
                    None,
                    (
                        f"max_blank must be an integer {_MIN_MAX_BLANK}..{_MAX_MAX_BLANK}, "
                        f"got {arguments.get('max_blank')!r}"
                    ),
                )
            return text, max_blank, None

        if _SPLIT_SENTINEL not in text:
            return text, _DEFAULT_MAX_BLANK, None

        document, suffix = text.split(_SPLIT_SENTINEL, maxsplit=1)
        if _SPLIT_SENTINEL in suffix:
            return None, None, "text contains more than one <<<TEXT_COLLAPSE_BLANK>>> sentinel"
        stripped = suffix.strip()
        if not stripped:
            return document, _DEFAULT_MAX_BLANK, None
        max_blank = cls._parse_max_blank(stripped)
        if max_blank is None:
            return (
                None,
                None,
                (f"max_blank must be an integer {_MIN_MAX_BLANK}..{_MAX_MAX_BLANK}, got {stripped!r}"),
            )
        return document, max_blank, None

    @staticmethod
    def _parse_max_blank(value: object) -> int | None:
        """Parse a bounded max_blank integer."""

        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            parsed = value
        elif isinstance(value, str) and value.strip().isdigit():
            parsed = int(value.strip())
        else:
            return None
        if not _MIN_MAX_BLANK <= parsed <= _MAX_MAX_BLANK:
            return None
        return parsed

    @staticmethod
    def _split_line_ending(line: str) -> tuple[str, str]:
        """Separate a line body from its original line ending."""

        if line.endswith("\r\n"):
            return line[:-2], "\r\n"
        if line.endswith("\n") or line.endswith("\r"):
            return line[:-1], line[-1]
        return line, ""

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
