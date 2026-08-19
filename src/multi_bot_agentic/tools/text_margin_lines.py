"""Deterministic bounded text line-margin tool.

Agents sometimes need fixed left and right margins around line-oriented
observations before the next model turn. This tool adds ASCII spaces to each
non-empty line, optionally skipping the first line, while preserving line
endings and enforcing hard input/output caps. It never executes code or makes
network requests. Safe for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2
workers.

The document and options may be supplied as separate arguments or as one
``text`` value split on ``<<<TEXT_MARGIN_LINES>>>`` with a
``left:right:skip_first`` suffix.
"""

from __future__ import annotations

from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_MIN_MARGIN: Final[int] = 0
_MAX_MARGIN: Final[int] = 200
_DEFAULT_MARGIN: Final[int] = 0
_DEFAULT_SKIP_FIRST: Final[bool] = False
_SPLIT_SENTINEL: Final[str] = "<<<TEXT_MARGIN_LINES>>>"
_TRUTHY: Final[frozenset[str]] = frozenset({"1", "true", "yes", "on"})
_FALSY: Final[frozenset[str]] = frozenset({"0", "false", "no", "off"})


class TextMarginLinesTool:
    """Add left and right ASCII-space margins to non-empty lines."""

    name = "text_margin_lines"
    description = (
        "Adds left/right ASCII-space margins to each non-empty line (0..200; "
        "optional skip_first); accepts text+options or <<<TEXT_MARGIN_LINES>>>; "
        "max 20_000 chars."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Add bounded margins to the invocation text."""

        document, left, right, skip_first, resolve_error = self._resolve_arguments(invocation.arguments)
        if resolve_error is not None:
            return self._fail(resolve_error, {})
        assert document is not None and left is not None and right is not None and skip_first is not None

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

        margin = (" " * left, " " * right)
        output_parts: list[str] = []
        margined_lines = 0
        output_chars = 0
        for index, line in enumerate(lines):
            if skip_first and index == 0:
                margined_line = line
            else:
                body, ending = self._split_line_ending(line)
                if body.strip():
                    margined_body = f"{margin[0]}{body}{margin[1]}"
                    if margined_body != body:
                        margined_lines += 1
                    margined_line = f"{margined_body}{ending}"
                else:
                    margined_line = f"{body}{ending}"

            output_chars += len(margined_line)
            if output_chars > _MAX_DOCUMENT_CHARS:
                return self._fail(
                    f"margined output exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                    {"chars": output_chars, "input_chars": len(document)},
                )
            output_parts.append(margined_line)

        result = "".join(output_parts)
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=result,
            metadata={
                "chars": len(result),
                "input_chars": len(document),
                "left": left,
                "right": right,
                "skip_first": skip_first,
                "lines": len(lines),
                "margined_lines": margined_lines,
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

    @classmethod
    def _resolve_arguments(
        cls,
        arguments: dict[str, object],
    ) -> tuple[str | None, int | None, int | None, bool | None, str | None]:
        """Resolve text and margin options from args or sentinel syntax."""

        text = str(arguments.get("text", ""))
        has_left = "left" in arguments
        has_right = "right" in arguments
        has_skip = "skip_first" in arguments

        if has_left or has_right or has_skip:
            left = cls._parse_margin(arguments["left"]) if has_left else _DEFAULT_MARGIN
            if left is None:
                return None, None, None, None, cls._margin_error("left", arguments["left"])
            right = cls._parse_margin(arguments["right"]) if has_right else _DEFAULT_MARGIN
            if right is None:
                return None, None, None, None, cls._margin_error("right", arguments["right"])
            skip_first = cls._parse_bool(arguments["skip_first"]) if has_skip else _DEFAULT_SKIP_FIRST
            if skip_first is None:
                return (
                    None,
                    None,
                    None,
                    None,
                    f"skip_first must be a boolean, got {arguments['skip_first']!r}",
                )
            return text, left, right, skip_first, None

        if _SPLIT_SENTINEL not in text:
            return text, _DEFAULT_MARGIN, _DEFAULT_MARGIN, _DEFAULT_SKIP_FIRST, None

        document, suffix = text.split(_SPLIT_SENTINEL, maxsplit=1)
        if _SPLIT_SENTINEL in suffix:
            return None, None, None, None, "text contains more than one <<<TEXT_MARGIN_LINES>>> sentinel"

        stripped = suffix.strip()
        if not stripped:
            return document, _DEFAULT_MARGIN, _DEFAULT_MARGIN, _DEFAULT_SKIP_FIRST, None
        parts = [part.strip() for part in stripped.split(":")]
        if len(parts) != 3:
            return None, None, None, None, "sentinel suffix must be left:right:skip_first"

        left = cls._parse_margin(parts[0])
        if left is None:
            return None, None, None, None, cls._margin_error("left", parts[0])
        right = cls._parse_margin(parts[1])
        if right is None:
            return None, None, None, None, cls._margin_error("right", parts[1])
        skip_first = cls._parse_bool(parts[2])
        if skip_first is None:
            return None, None, None, None, f"skip_first must be a boolean, got {parts[2]!r}"
        return document, left, right, skip_first, None

    @staticmethod
    def _parse_margin(value: object) -> int | None:
        """Coerce a margin argument to an allowed integer."""

        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value if _MIN_MARGIN <= value <= _MAX_MARGIN else None
        if isinstance(value, str):
            text = value.strip()
            if text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
                parsed = int(text)
                return parsed if _MIN_MARGIN <= parsed <= _MAX_MARGIN else None
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

    @staticmethod
    def _margin_error(name: str, value: object) -> str:
        """Build a consistent margin validation message."""

        return f"{name} must be an integer {_MIN_MARGIN}..{_MAX_MARGIN}, got {value!r}"

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
