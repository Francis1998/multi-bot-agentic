"""Deterministic bounded text line centering tool.

Agents sometimes need each non-empty line centered to a fixed column width
before aligning code blocks, headings, or quoted observations. Asking a model
to center lines can drop blank lines or mis-count widths. This tool pads both
sides of each non-empty line with ASCII spaces (default width 80), optionally
skipping the first line, with hard input and output caps. It never executes code
or makes network requests. Safe for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x /
Kimi K2 workers.

The document and options may be supplied as separate ``text`` / ``width`` /
``skip_first`` arguments or as a single ``text`` value split on
``<<<TEXT_CENTER_LINES>>>``.
"""

from __future__ import annotations

from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_DEFAULT_WIDTH: Final[int] = 80
_MIN_WIDTH: Final[int] = 1
_MAX_WIDTH: Final[int] = 200
_DEFAULT_SKIP_FIRST: Final[bool] = False
_SPLIT_SENTINEL: Final[str] = "<<<TEXT_CENTER_LINES>>>"
_TRUTHY: Final[frozenset[str]] = frozenset({"1", "true", "yes", "on"})
_FALSY: Final[frozenset[str]] = frozenset({"0", "false", "no", "off"})


class TextCenterLinesTool:
    """Center each non-empty line to a target width with ASCII spaces."""

    name = "text_center_lines"
    description = (
        "Centers each non-empty line to width with ASCII spaces (default width 80; "
        "optional skip_first); accepts text+options or <<<TEXT_CENTER_LINES>>>; "
        "max 20_000 chars."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Center non-empty lines in the invocation text."""

        document, width, skip_first, resolve_error = self._resolve_arguments(invocation.arguments)
        if resolve_error is not None:
            return self._fail(resolve_error, {})
        assert document is not None and width is not None and skip_first is not None

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

        centered_parts: list[str] = []
        centered_lines = 0
        output_chars = 0
        for index, line in enumerate(lines):
            if skip_first and index == 0:
                centered_line = line
            else:
                body, ending = self._split_line_ending(line)
                if body.strip():
                    centered_body = self._center_line(body, width)
                    if centered_body != body:
                        centered_lines += 1
                    centered_line = f"{centered_body}{ending}"
                else:
                    centered_line = f"{body}{ending}"
            output_chars += len(centered_line)
            if output_chars > _MAX_DOCUMENT_CHARS:
                return self._fail(
                    f"centered output exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                    {"chars": output_chars, "input_chars": len(document)},
                )
            centered_parts.append(centered_line)

        centered = "".join(centered_parts)
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=centered,
            metadata={
                "chars": len(centered),
                "input_chars": len(document),
                "width": width,
                "side": "both",
                "skip_first": skip_first,
                "lines": len(lines),
                "centered_lines": centered_lines,
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
    def _center_line(body: str, width: int) -> str:
        """Center a single line body to the requested width."""

        current = len(body)
        if current >= width:
            return body
        pad_count = width - current
        left_pad = pad_count // 2
        right_pad = pad_count - left_pad
        return (" " * left_pad) + body + (" " * right_pad)

    @classmethod
    def _resolve_arguments(
        cls,
        arguments: dict[str, object],
    ) -> tuple[str | None, int | None, bool | None, str | None]:
        """Resolve text, width, and skip_first from args or sentinel syntax."""

        text = str(arguments.get("text", ""))
        has_width = "width" in arguments
        has_skip = "skip_first" in arguments

        if has_width or has_skip:
            width = cls._parse_width(arguments["width"]) if has_width else _DEFAULT_WIDTH
            if width is None:
                return (
                    None,
                    None,
                    None,
                    f"width must be an integer {_MIN_WIDTH}..{_MAX_WIDTH}, got {arguments['width']!r}",
                )
            skip_first = cls._parse_bool(arguments["skip_first"]) if has_skip else _DEFAULT_SKIP_FIRST
            if skip_first is None:
                return None, None, None, f"skip_first must be a boolean, got {arguments['skip_first']!r}"
            return text, width, skip_first, None

        if _SPLIT_SENTINEL not in text:
            return text, _DEFAULT_WIDTH, _DEFAULT_SKIP_FIRST, None

        document, remainder = text.split(_SPLIT_SENTINEL, maxsplit=1)
        if _SPLIT_SENTINEL in remainder:
            return None, None, None, "text contains more than one <<<TEXT_CENTER_LINES>>> sentinel"

        stripped = remainder.strip()
        if not stripped:
            return document, _DEFAULT_WIDTH, _DEFAULT_SKIP_FIRST, None
        parts = [part.strip() for part in stripped.split(":")]
        if len(parts) > 2:
            return None, None, None, "sentinel suffix must be width or width:skip_first"
        width = cls._parse_width(parts[0])
        if width is None:
            return (
                None,
                None,
                None,
                f"width must be an integer {_MIN_WIDTH}..{_MAX_WIDTH}, got {parts[0]!r}",
            )
        skip_first = _DEFAULT_SKIP_FIRST
        if len(parts) == 2:
            parsed_skip = cls._parse_bool(parts[1])
            if parsed_skip is None:
                return None, None, None, f"skip_first must be a boolean, got {parts[1]!r}"
            skip_first = parsed_skip
        return document, width, skip_first, None

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
