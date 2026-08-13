"""Deterministic text indentation tool.

Agents often need every non-empty line of a pasted block indented before nesting
it in a code fence, YAML list, or quoted reply. Asking a model to add spaces can
drop blank lines or invent uneven widths. This tool prepends a fixed number of
spaces to each non-empty line (default 2, max 32), optionally skipping the first
line, with a hard input cap. It never executes code or makes network requests.
Safe for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.

The document and options may be supplied as separate ``text`` / ``spaces`` /
``skip_first`` arguments or as a single ``text`` value split on
``<<<TEXT_INDENT>>>``.
"""

from __future__ import annotations

from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_DEFAULT_SPACES: Final[int] = 2
_MIN_SPACES: Final[int] = 0
_MAX_SPACES: Final[int] = 32
_DEFAULT_SKIP_FIRST: Final[bool] = False
_SPLIT_SENTINEL: Final[str] = "<<<TEXT_INDENT>>>"
_TRUTHY: Final[frozenset[str]] = frozenset({"1", "true", "yes", "on"})
_FALSY: Final[frozenset[str]] = frozenset({"0", "false", "no", "off"})


class TextIndentTool:
    """Indent every non-empty line by a fixed number of spaces."""

    name = "text_indent"
    description = (
        "Indents every non-empty line by N spaces (default 2, max 32; optional skip_first); "
        "accepts text+spaces+skip_first or <<<TEXT_INDENT>>>; max 20_000 chars."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Indent non-empty lines in the invocation text."""

        document, spaces, skip_first, resolve_error = self._resolve_arguments(invocation.arguments)
        if resolve_error is not None:
            return self._fail(resolve_error, {})
        assert document is not None and spaces is not None and skip_first is not None

        if not document:
            return self._fail("text is empty", {})
        if len(document) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"text exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(document)},
            )

        prefix = " " * spaces
        lines = document.splitlines(keepends=True)
        if not lines and document:
            # splitlines drops a final empty segment; treat bare text as one line.
            lines = [document]

        indented_parts: list[str] = []
        for index, line in enumerate(lines):
            if skip_first and index == 0:
                indented_parts.append(line)
                continue
            if line.endswith("\r\n"):
                body, ending = line[:-2], "\r\n"
            elif line.endswith("\n") or line.endswith("\r"):
                body, ending = line[:-1], line[-1]
            else:
                body, ending = line, ""
            if body.strip():
                indented_parts.append(f"{prefix}{body}{ending}")
            else:
                indented_parts.append(f"{body}{ending}")

        indented = "".join(indented_parts)
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=indented,
            metadata={
                "chars": len(indented),
                "input_chars": len(document),
                "spaces": spaces,
                "skip_first": skip_first,
                "lines": len(lines),
            },
        )

    @classmethod
    def _resolve_arguments(
        cls,
        arguments: dict[str, object],
    ) -> tuple[str | None, int | None, bool | None, str | None]:
        """Resolve text, spaces, and skip_first from args or sentinel syntax."""

        text = str(arguments.get("text", ""))
        has_spaces = "spaces" in arguments
        has_skip = "skip_first" in arguments

        if has_spaces or has_skip:
            if has_spaces:
                spaces = cls._parse_spaces(arguments["spaces"])
                if spaces is None:
                    return (
                        None,
                        None,
                        None,
                        f"spaces must be an integer {_MIN_SPACES}..{_MAX_SPACES}, got {arguments['spaces']!r}",
                    )
            else:
                spaces = _DEFAULT_SPACES
            if has_skip:
                skip_first = cls._parse_bool(arguments["skip_first"])
                if skip_first is None:
                    return (
                        None,
                        None,
                        None,
                        f"skip_first must be a boolean, got {arguments['skip_first']!r}",
                    )
            else:
                skip_first = _DEFAULT_SKIP_FIRST
            return text, spaces, skip_first, None

        if _SPLIT_SENTINEL not in text:
            return text, _DEFAULT_SPACES, _DEFAULT_SKIP_FIRST, None

        document, remainder = text.split(_SPLIT_SENTINEL, maxsplit=1)
        if _SPLIT_SENTINEL in remainder:
            return None, None, None, "text contains more than one <<<TEXT_INDENT>>> sentinel"

        spaces, skip_first, parse_error = cls._parse_sentinel_remainder(remainder)
        if parse_error is not None:
            return None, None, None, parse_error
        return document, spaces, skip_first, None

    @classmethod
    def _parse_sentinel_remainder(
        cls,
        remainder: str,
    ) -> tuple[int | None, bool | None, str | None]:
        """Parse optional spaces/skip_first from a sentinel suffix."""

        stripped = remainder.strip()
        if not stripped:
            return _DEFAULT_SPACES, _DEFAULT_SKIP_FIRST, None

        if ":" in stripped:
            spaces_text, skip_text = stripped.split(":", maxsplit=1)
            spaces = cls._parse_spaces(spaces_text.strip())
            if spaces is None:
                return (
                    None,
                    None,
                    f"spaces must be an integer {_MIN_SPACES}..{_MAX_SPACES}, got {spaces_text.strip()!r}",
                )
            skip_first = cls._parse_bool(skip_text.strip())
            if skip_first is None:
                return None, None, f"skip_first must be a boolean, got {skip_text.strip()!r}"
            return spaces, skip_first, None

        spaces = cls._parse_spaces(stripped)
        if spaces is None:
            return (
                None,
                None,
                f"spaces must be an integer {_MIN_SPACES}..{_MAX_SPACES}, got {stripped!r}",
            )
        return spaces, _DEFAULT_SKIP_FIRST, None

    @staticmethod
    def _parse_spaces(value: object) -> int | None:
        """Coerce a spaces argument to an allowed integer."""

        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value if _MIN_SPACES <= value <= _MAX_SPACES else None
        if isinstance(value, str):
            text = value.strip()
            if text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
                parsed = int(text)
                return parsed if _MIN_SPACES <= parsed <= _MAX_SPACES else None
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
