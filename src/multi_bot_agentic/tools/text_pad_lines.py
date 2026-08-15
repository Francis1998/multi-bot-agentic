"""Deterministic bounded text line padding tool.

Agents sometimes need each non-empty line padded to a fixed column width before
aligning code blocks, tables, or quoted observations. Asking a model to pad lines
can drop blank lines or mis-count widths. This tool pads each non-empty line to a
target width with leading and/or trailing ASCII spaces (default width 80, side
right), optionally skipping the first line, with a hard input cap. It never
executes code or makes network requests. Safe for GPT-5.5 / Claude Sonnet 4.6 /
Gemini 3.x / Kimi K2 workers.

The document and options may be supplied as separate ``text`` / ``width`` /
``side`` / ``skip_first`` arguments or as a single ``text`` value split on
``<<<TEXT_PAD_LINES>>>``.
"""

from __future__ import annotations

from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_DEFAULT_WIDTH: Final[int] = 80
_MIN_WIDTH: Final[int] = 1
_MAX_WIDTH: Final[int] = 200
_DEFAULT_SIDE: Final[str] = "right"
_ALLOWED_SIDES: Final[frozenset[str]] = frozenset({"left", "right", "both"})
_DEFAULT_SKIP_FIRST: Final[bool] = False
_SPLIT_SENTINEL: Final[str] = "<<<TEXT_PAD_LINES>>>"
_TRUTHY: Final[frozenset[str]] = frozenset({"1", "true", "yes", "on"})
_FALSY: Final[frozenset[str]] = frozenset({"0", "false", "no", "off"})


class TextPadLinesTool:
    """Pad each non-empty line to a target width with ASCII spaces."""

    name = "text_pad_lines"
    description = (
        "Pads each non-empty line to width with left/right/both ASCII spaces "
        "(default width 80, side right; optional skip_first); accepts text+options "
        "or <<<TEXT_PAD_LINES>>>; max 20_000 chars."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Pad non-empty lines in the invocation text."""

        document, width, side, skip_first, resolve_error = self._resolve_arguments(invocation.arguments)
        if resolve_error is not None:
            return self._fail(resolve_error, {})
        assert document is not None and width is not None and side is not None and skip_first is not None

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

        padded_parts: list[str] = []
        padded_lines = 0
        for index, line in enumerate(lines):
            if skip_first and index == 0:
                padded_parts.append(line)
                continue
            if line.endswith("\r\n"):
                body, ending = line[:-2], "\r\n"
            elif line.endswith("\n") or line.endswith("\r"):
                body, ending = line[:-1], line[-1]
            else:
                body, ending = line, ""
            if body.strip():
                padded_body = self._pad_line(body, width, side)
                if padded_body != body:
                    padded_lines += 1
                padded_parts.append(f"{padded_body}{ending}")
            else:
                padded_parts.append(f"{body}{ending}")

        padded = "".join(padded_parts)
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=padded,
            metadata={
                "chars": len(padded),
                "input_chars": len(document),
                "width": width,
                "side": side,
                "skip_first": skip_first,
                "lines": len(lines),
                "padded_lines": padded_lines,
            },
        )

    @staticmethod
    def _pad_line(body: str, width: int, side: str) -> str:
        """Pad a single line body to the requested width."""

        current = len(body)
        if current >= width:
            return body
        pad_count = width - current
        if side == "left":
            return (" " * pad_count) + body
        if side == "both":
            left_pad = pad_count // 2
            right_pad = pad_count - left_pad
            return (" " * left_pad) + body + (" " * right_pad)
        return body + (" " * pad_count)

    @classmethod
    def _resolve_arguments(
        cls,
        arguments: dict[str, object],
    ) -> tuple[str | None, int | None, str | None, bool | None, str | None]:
        """Resolve text, width, side, and skip_first from args or sentinel syntax."""

        text = str(arguments.get("text", ""))
        has_width = "width" in arguments
        has_side = "side" in arguments
        has_skip = "skip_first" in arguments

        if has_width or has_side or has_skip:
            if has_width:
                width = cls._parse_width(arguments["width"])
                if width is None:
                    return (
                        None,
                        None,
                        None,
                        None,
                        f"width must be an integer {_MIN_WIDTH}..{_MAX_WIDTH}, got {arguments['width']!r}",
                    )
            else:
                width = _DEFAULT_WIDTH
            if has_side:
                side = cls._parse_side(arguments["side"])
                if side is None:
                    return (
                        None,
                        None,
                        None,
                        None,
                        f"side must be left, right, or both, got {arguments['side']!r}",
                    )
            else:
                side = _DEFAULT_SIDE
            if has_skip:
                skip_first = cls._parse_bool(arguments["skip_first"])
                if skip_first is None:
                    return (
                        None,
                        None,
                        None,
                        None,
                        f"skip_first must be a boolean, got {arguments['skip_first']!r}",
                    )
            else:
                skip_first = _DEFAULT_SKIP_FIRST
            return text, width, side, skip_first, None

        if _SPLIT_SENTINEL not in text:
            return text, _DEFAULT_WIDTH, _DEFAULT_SIDE, _DEFAULT_SKIP_FIRST, None

        document, remainder = text.split(_SPLIT_SENTINEL, maxsplit=1)
        if _SPLIT_SENTINEL in remainder:
            return None, None, None, None, "text contains more than one <<<TEXT_PAD_LINES>>> sentinel"

        width, side, skip_first, parse_error = cls._parse_sentinel_remainder(remainder)
        if parse_error is not None:
            return None, None, None, None, parse_error
        return document, width, side, skip_first, None

    @classmethod
    def _parse_sentinel_remainder(
        cls,
        remainder: str,
    ) -> tuple[int | None, str | None, bool | None, str | None]:
        """Parse optional width/side/skip_first from a sentinel suffix."""

        stripped = remainder.strip()
        if not stripped:
            return _DEFAULT_WIDTH, _DEFAULT_SIDE, _DEFAULT_SKIP_FIRST, None

        parts = [part.strip() for part in stripped.split(":")]
        width = cls._parse_width(parts[0])
        if width is None:
            return (
                None,
                None,
                None,
                f"width must be an integer {_MIN_WIDTH}..{_MAX_WIDTH}, got {parts[0]!r}",
            )

        side = _DEFAULT_SIDE
        skip_first = _DEFAULT_SKIP_FIRST
        if len(parts) == 1:
            return width, side, skip_first, None
        if len(parts) == 2:
            if parts[1].lower() in _ALLOWED_SIDES:
                parsed_side = cls._parse_side(parts[1])
                if parsed_side is None:
                    return None, None, None, f"side must be left, right, or both, got {parts[1]!r}"
                return width, parsed_side, skip_first, None
            parsed_skip = cls._parse_bool(parts[1])
            if parsed_skip is None:
                return None, None, None, f"skip_first must be a boolean, got {parts[1]!r}"
            return width, side, parsed_skip, None

        parsed_side = cls._parse_side(parts[1])
        if parsed_side is None:
            return None, None, None, f"side must be left, right, or both, got {parts[1]!r}"
        parsed_skip = cls._parse_bool(parts[2])
        if parsed_skip is None:
            return None, None, None, f"skip_first must be a boolean, got {parts[2]!r}"
        return width, parsed_side, parsed_skip, None

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
    def _parse_side(value: object) -> str | None:
        """Coerce a side argument to an allowed value."""

        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in _ALLOWED_SIDES:
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
