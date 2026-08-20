"""Deterministic bounded text line-justification tool.

Agents sometimes need line-oriented observations aligned to a fixed width
without asking a model to count columns or distribute spaces. This tool formats
non-empty lines with left, right, center, or full justification, preserves line
endings, and enforces input/output caps. It never executes code or makes network
requests. Safe for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.

Arguments may be supplied separately or in one ``text`` value split on
``<<<TEXT_JUSTIFY_LINES>>>`` with a ``width:alignment:skip_first`` suffix.
"""

from __future__ import annotations

from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_DEFAULT_WIDTH: Final[int] = 80
_MIN_WIDTH: Final[int] = 1
_MAX_WIDTH: Final[int] = 500
_DEFAULT_ALIGNMENT: Final[str] = "left"
_ALIGNMENTS: Final[frozenset[str]] = frozenset({"left", "right", "center", "justify"})
_DEFAULT_SKIP_FIRST: Final[bool] = False
_SPLIT_SENTINEL: Final[str] = "<<<TEXT_JUSTIFY_LINES>>>"
_TRUTHY: Final[frozenset[str]] = frozenset({"1", "true", "yes", "on"})
_FALSY: Final[frozenset[str]] = frozenset({"0", "false", "no", "off"})


class TextJustifyLinesTool:
    """Align each non-empty line to a bounded target width."""

    name = "text_justify_lines"
    description = (
        "Formats non-empty lines with left/right/center/justify alignment "
        "(default width 80, max 500; optional skip_first); accepts text+options "
        "or <<<TEXT_JUSTIFY_LINES>>>; max 20_000 chars."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Format non-empty lines according to the requested alignment."""

        document, width, alignment, skip_first, resolve_error = self._resolve_arguments(invocation.arguments)
        if resolve_error is not None:
            return self._fail(resolve_error, {})
        assert document is not None and width is not None and alignment is not None and skip_first is not None

        if not document:
            return self._fail("text is empty", {})
        if len(document) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"text exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(document)},
            )

        lines = document.splitlines(keepends=True)
        if not lines and document:
            lines = [document]

        output_parts: list[str] = []
        formatted_lines = 0
        output_chars = 0
        for index, line in enumerate(lines):
            if skip_first and index == 0:
                formatted_line = line
            else:
                body, ending = self._split_line_ending(line)
                if body.strip():
                    formatted_body = self._format_line(body, width, alignment)
                    if formatted_body != body:
                        formatted_lines += 1
                    formatted_line = f"{formatted_body}{ending}"
                else:
                    formatted_line = f"{body}{ending}"

            output_chars += len(formatted_line)
            if output_chars > _MAX_DOCUMENT_CHARS:
                return self._fail(
                    f"formatted output exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                    {"chars": output_chars, "input_chars": len(document)},
                )
            output_parts.append(formatted_line)

        formatted = "".join(output_parts)
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=formatted,
            metadata={
                "alignment": alignment,
                "chars": len(formatted),
                "formatted_lines": formatted_lines,
                "input_chars": len(document),
                "lines": len(lines),
                "skip_first": skip_first,
                "width": width,
            },
        )

    @staticmethod
    def _split_line_ending(line: str) -> tuple[str, str]:
        """Separate a line body from its original line ending."""

        if line.endswith("\r\n"):
            return line[:-2], "\r\n"
        if line.endswith("\n") or line.endswith("\r"):
            return line[:-1], line[-1]
        return line, ""

    @staticmethod
    def _format_line(body: str, width: int, alignment: str) -> str:
        """Format one non-empty line without truncating content."""

        if alignment == "justify":
            return TextJustifyLinesTool._fully_justify(body, width)
        if len(body) >= width:
            return body

        padding = width - len(body)
        if alignment == "right":
            return (" " * padding) + body
        if alignment == "center":
            left = padding // 2
            return (" " * left) + body + (" " * (padding - left))
        return body + (" " * padding)

    @staticmethod
    def _fully_justify(body: str, width: int) -> str:
        """Distribute spaces across word gaps, with extra spaces on the left."""

        words = body.split()
        if len(words) == 1:
            return words[0] + (" " * max(0, width - len(words[0])))

        minimum_width = sum(len(word) for word in words) + len(words) - 1
        if minimum_width > width:
            return body

        total_spaces = width - sum(len(word) for word in words)
        gap_width, extra = divmod(total_spaces, len(words) - 1)
        parts: list[str] = []
        for index, word in enumerate(words[:-1]):
            parts.append(word)
            parts.append(" " * (gap_width + (1 if index < extra else 0)))
        parts.append(words[-1])
        return "".join(parts)

    @classmethod
    def _resolve_arguments(
        cls,
        arguments: dict[str, object],
    ) -> tuple[str | None, int | None, str | None, bool | None, str | None]:
        """Resolve text and formatting options from args or sentinel syntax."""

        text = str(arguments.get("text", ""))
        has_width = "width" in arguments
        alignment_keys = [key for key in ("alignment", "align", "mode") if key in arguments]
        has_skip = "skip_first" in arguments
        if len(alignment_keys) > 1:
            return None, None, None, None, "provide only one of alignment, align, or mode"

        if has_width or alignment_keys or has_skip:
            width = cls._parse_width(arguments["width"]) if has_width else _DEFAULT_WIDTH
            if width is None:
                return (
                    None,
                    None,
                    None,
                    None,
                    f"width must be an integer {_MIN_WIDTH}..{_MAX_WIDTH}, got {arguments['width']!r}",
                )

            if alignment_keys:
                key = alignment_keys[0]
                alignment = cls._parse_alignment(arguments[key])
                if alignment is None:
                    return (
                        None,
                        None,
                        None,
                        None,
                        f"alignment must be left, right, center, or justify, got {arguments[key]!r}",
                    )
            else:
                alignment = _DEFAULT_ALIGNMENT

            skip_first = cls._parse_bool(arguments["skip_first"]) if has_skip else _DEFAULT_SKIP_FIRST
            if skip_first is None:
                return (
                    None,
                    None,
                    None,
                    None,
                    f"skip_first must be a boolean, got {arguments['skip_first']!r}",
                )
            return text, width, alignment, skip_first, None

        if _SPLIT_SENTINEL not in text:
            return text, _DEFAULT_WIDTH, _DEFAULT_ALIGNMENT, _DEFAULT_SKIP_FIRST, None

        document, suffix = text.split(_SPLIT_SENTINEL, maxsplit=1)
        if _SPLIT_SENTINEL in suffix:
            return None, None, None, None, "text contains more than one <<<TEXT_JUSTIFY_LINES>>> sentinel"
        return cls._parse_sentinel(document, suffix)

    @classmethod
    def _parse_sentinel(
        cls,
        document: str,
        suffix: str,
    ) -> tuple[str | None, int | None, str | None, bool | None, str | None]:
        """Parse a width:alignment:skip_first sentinel suffix."""

        stripped = suffix.strip()
        if not stripped:
            return document, _DEFAULT_WIDTH, _DEFAULT_ALIGNMENT, _DEFAULT_SKIP_FIRST, None
        parts = [part.strip() for part in stripped.split(":")]
        if not 1 <= len(parts) <= 3:
            return None, None, None, None, "sentinel suffix must be width[:alignment[:skip_first]]"

        width = cls._parse_width(parts[0])
        if width is None:
            return (
                None,
                None,
                None,
                None,
                f"width must be an integer {_MIN_WIDTH}..{_MAX_WIDTH}, got {parts[0]!r}",
            )

        alignment = _DEFAULT_ALIGNMENT
        if len(parts) >= 2:
            parsed_alignment = cls._parse_alignment(parts[1])
            if parsed_alignment is None:
                return (
                    None,
                    None,
                    None,
                    None,
                    f"alignment must be left, right, center, or justify, got {parts[1]!r}",
                )
            alignment = parsed_alignment

        skip_first = _DEFAULT_SKIP_FIRST
        if len(parts) == 3:
            parsed_skip = cls._parse_bool(parts[2])
            if parsed_skip is None:
                return None, None, None, None, f"skip_first must be a boolean, got {parts[2]!r}"
            skip_first = parsed_skip
        return document, width, alignment, skip_first, None

    @staticmethod
    def _parse_width(value: object) -> int | None:
        """Coerce a width argument to an allowed integer."""

        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value if _MIN_WIDTH <= value <= _MAX_WIDTH else None
        if isinstance(value, str):
            text = value.strip()
            if text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
                parsed = int(text)
                return parsed if _MIN_WIDTH <= parsed <= _MAX_WIDTH else None
        return None

    @staticmethod
    def _parse_alignment(value: object) -> str | None:
        """Normalize one alignment option."""

        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in _ALIGNMENTS:
                return normalized
        return None

    @staticmethod
    def _parse_bool(value: object) -> bool | None:
        """Coerce a boolean-like skip_first argument."""

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
