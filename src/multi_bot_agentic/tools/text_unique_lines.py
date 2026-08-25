"""Deterministic order-preserving unique-lines tool.

Agents often need to dedupe noisy logs or candidate lists without sorting.
This tool keeps the first occurrence of each line (optionally stripped for
comparison), preserves original line endings, and never executes code or
makes network requests. Safe for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x /
Kimi K2 workers.

Arguments may be supplied separately or in one ``text`` value split on
``<<<TEXT_UNIQUE_LINES>>>`` with a ``strip`` suffix (default true).
Unlike ``text_sort_lines`` with ``unique=true``, this tool does not reorder.
"""

from __future__ import annotations

from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_DEFAULT_STRIP: Final[bool] = True
_SPLIT_SENTINEL: Final[str] = "<<<TEXT_UNIQUE_LINES>>>"
_TRUTHY: Final[frozenset[str]] = frozenset({"1", "true", "yes", "on"})
_FALSY: Final[frozenset[str]] = frozenset({"0", "false", "no", "off"})


class TextUniqueLinesTool:
    """Deduplicate lines while preserving first-seen order."""

    name = "text_unique_lines"
    description = (
        "Deduplicates lines in first-seen order (optional strip for compare, "
        "default true); accepts <<<TEXT_UNIQUE_LINES>>>; max 20_000 chars."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Deduplicate lines in the invocation text."""

        document, strip, resolve_error = self._resolve_arguments(invocation.arguments)
        if resolve_error is not None:
            return self._fail(resolve_error, {})
        assert document is not None and strip is not None

        if not document.strip():
            return self._fail("text is empty", {})
        if len(document) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"text exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(document)},
            )

        lines = document.splitlines(keepends=True)
        output_parts: list[str] = []
        seen: set[str] = set()
        kept = 0
        dropped = 0
        output_chars = 0

        for line in lines:
            body, ending = self._split_line_ending(line)
            key = body.strip() if strip else body
            if key in seen:
                dropped += 1
                continue
            seen.add(key)
            emitted = f"{body}{ending}"
            output_chars += len(emitted)
            if output_chars > _MAX_DOCUMENT_CHARS:
                return self._fail(
                    f"unique output exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                    {"chars": output_chars, "input_chars": len(document)},
                )
            output_parts.append(emitted)
            kept += 1

        content = "".join(output_parts)
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=content,
            metadata={
                "chars": len(content),
                "input_chars": len(document),
                "lines": len(lines),
                "kept": kept,
                "dropped": dropped,
                "strip": strip,
            },
        )

    @classmethod
    def _resolve_arguments(cls, arguments: dict[str, object]) -> tuple[str | None, bool | None, str | None]:
        """Resolve text and strip from explicit args or sentinel syntax."""

        text = str(arguments.get("text", ""))
        if "strip" in arguments:
            strip = cls._parse_bool(arguments.get("strip"))
            if strip is None:
                return (
                    None,
                    None,
                    f"strip must be a boolean, got {arguments.get('strip')!r}",
                )
            return text, strip, None

        if _SPLIT_SENTINEL not in text:
            return text, _DEFAULT_STRIP, None

        document, suffix = text.split(_SPLIT_SENTINEL, maxsplit=1)
        if _SPLIT_SENTINEL in suffix:
            return None, None, "text contains more than one <<<TEXT_UNIQUE_LINES>>> sentinel"
        stripped = suffix.strip()
        if not stripped:
            return document, _DEFAULT_STRIP, None
        strip = cls._parse_bool(stripped)
        if strip is None:
            return None, None, f"strip must be a boolean, got {stripped!r}"
        return document, strip, None

    @staticmethod
    def _parse_bool(value: object) -> bool | None:
        """Parse a truthy/falsy bool."""

        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in _TRUTHY:
                return True
            if lowered in _FALSY:
                return False
        return None

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
