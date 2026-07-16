"""Unified text-diff tool.

Agent runs routinely need to compare two observations, two tool outputs, or a
before/after snapshot: a config rewrite, a redacted document, or a checklist
delta. Asking a language model to invent a diff is unreliable (hallucinated
hunks, reordered lines, dropped context). This tool produces a deterministic
unified diff via :mod:`difflib`, with bounded input size and a structured
failure for empty or oversized sides. It never executes code and never makes a
network request, matching the ``datetime``, ``duration``, ``hash``, ``slugify``,
and ``json_format`` tool contracts.

Because the decision engine only forwards a single ``text`` payload from
``TOOL:diff:<payload>``, the two sides may be supplied either as separate
``text`` / ``other`` arguments (tests and programmatic callers) or as a single
``text`` value split on the sentinel ``\\n<<<DIFF>>>\\n``.
"""

from __future__ import annotations

import difflib
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_SIDE_CHARS: Final[int] = 20_000
_MAX_OUTPUT_LINES: Final[int] = 2_000
_DEFAULT_CONTEXT: Final[int] = 3
_MAX_CONTEXT: Final[int] = 32
_SPLIT_SENTINEL: Final[str] = "\n<<<DIFF>>>\n"


class DiffTool:
    """Produce a unified diff between two text sides."""

    name = "diff"
    description = (
        "Produces a unified diff between two texts (text+other, or text split on <<<DIFF>>>, optional context)."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Diff the two text sides supplied in the invocation.

        Args:
            invocation: Tool invocation whose ``text`` and optional ``other``
                arguments hold the left/right sides (or ``text`` alone split on
                ``<<<DIFF>>>``), and whose optional ``context`` argument sets
                the number of unified-diff context lines (default 3).

        Returns:
            Tool result whose ``content`` is the unified diff (empty string when
            identical), or ``ok=False`` and an explanation when a side is
            missing/empty/oversized, the split is ambiguous, or ``context`` is
            invalid.
        """

        left, right, error = self._resolve_sides(invocation.arguments)
        if error is not None:
            return self._fail(error, {})

        assert left is not None and right is not None
        if len(left) > _MAX_SIDE_CHARS:
            return self._fail(
                f"left text exceeds max_chars={_MAX_SIDE_CHARS}",
                {"chars": len(left)},
            )
        if len(right) > _MAX_SIDE_CHARS:
            return self._fail(
                f"right text exceeds max_chars={_MAX_SIDE_CHARS}",
                {"chars": len(right)},
            )

        context = invocation.arguments.get("context", _DEFAULT_CONTEXT)
        parsed_context = self._parse_context(context)
        if parsed_context is None:
            return self._fail(
                f"context must be an integer 0..{_MAX_CONTEXT}, got {context!r}",
                {"context": str(context)},
            )

        left_lines = left.splitlines()
        right_lines = right.splitlines()
        diff_lines = list(
            difflib.unified_diff(
                left_lines,
                right_lines,
                fromfile="a",
                tofile="b",
                lineterm="",
                n=parsed_context,
            )
        )
        if len(diff_lines) > _MAX_OUTPUT_LINES:
            return self._fail(
                f"diff exceeds max_output_lines={_MAX_OUTPUT_LINES}",
                {"lines": len(diff_lines)},
            )

        added = sum(1 for line in diff_lines if line.startswith("+") and not line.startswith("+++"))
        removed = sum(1 for line in diff_lines if line.startswith("-") and not line.startswith("---"))
        identical = not diff_lines
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content="\n".join(diff_lines),
            metadata={
                "added": added,
                "removed": removed,
                "identical": identical,
                "context": parsed_context,
            },
        )

    @classmethod
    def _resolve_sides(cls, arguments: dict[str, object]) -> tuple[str | None, str | None, str | None]:
        """Resolve left/right sides from ``text``/``other`` or the split sentinel.

        Args:
            arguments: Tool invocation arguments.

        Returns:
            ``(left, right, error)`` — exactly one of the sides-pair or the error
            string is populated.
        """

        text = str(arguments.get("text", ""))
        if "other" in arguments:
            other = str(arguments.get("other", ""))
            if not text and not other:
                return None, None, "both text sides are empty"
            if not text:
                return None, None, "left text is empty"
            if not other:
                return None, None, "right text is empty"
            return text, other, None

        if _SPLIT_SENTINEL not in text:
            return None, None, (f"diff requires text+other arguments, or a single text split on {_SPLIT_SENTINEL!r}")
        left, right = text.split(_SPLIT_SENTINEL, maxsplit=1)
        if _SPLIT_SENTINEL in right:
            return None, None, "text contains more than one <<<DIFF>>> sentinel"
        if not left:
            return None, None, "left text is empty"
        if not right:
            return None, None, "right text is empty"
        return left, right, None

    @staticmethod
    def _parse_context(value: object) -> int | None:
        """Coerce a ``context`` argument to an allowed integer.

        Args:
            value: Raw ``context`` argument.

        Returns:
            Context line count in ``0.._MAX_CONTEXT``, or None when invalid.
        """

        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value if 0 <= value <= _MAX_CONTEXT else None
        if isinstance(value, str):
            text = value.strip()
            if text.isdigit():
                parsed = int(text)
                return parsed if 0 <= parsed <= _MAX_CONTEXT else None
        return None

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result.

        Args:
            message: Human-readable failure explanation.
            metadata: Structured metadata for the failure.

        Returns:
            A ``ok=False`` tool result carrying the message and metadata.
        """

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
