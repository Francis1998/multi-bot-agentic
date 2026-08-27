"""JSON Lines parser for dataset / LLM agent workflows.

HuggingFace-datasets-style agents often receive JSONL blobs and need a
deterministic JSON array before the next model turn. Asking an LLM to parse
JSONL is fragile on large multi-line payloads. This tool validates JSON Lines
text with the stdlib ``json`` module and returns a pretty-printed JSON array.
It never executes code and never makes network requests. Safe for GPT-5.5 /
Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.
"""

from __future__ import annotations

import json
import math
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_MAX_LINES: Final[int] = 500
_DEFAULT_MODE: Final[str] = "objects"
_MODES: Final[frozenset[str]] = frozenset({"objects", "any"})


def _reject_non_finite(token: str) -> float:
    """Reject non-standard ``NaN``/``Infinity``/``-Infinity`` JSON tokens."""

    raise ValueError(f"{token} is not valid JSON")


def _parse_finite_float(token: str) -> float:
    """Parse a JSON float token, rejecting values that overflow to infinity."""

    value = float(token)
    if not math.isfinite(value):
        raise ValueError(f"{token} overflows to a non-finite number and is not valid JSON")
    return value


class JsonlParseTool:
    """Parse JSON Lines text into a pretty JSON array."""

    name = "jsonl_parse"
    description = (
        "Parses JSON Lines text into a pretty JSON array (mode objects default or any; max 500 lines / 20_000 chars)."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Parse JSONL from the invocation text.

        Args:
            invocation: Tool invocation whose ``text`` argument holds JSON
                Lines and whose optional ``mode`` is ``objects`` (default) or
                ``any``.

        Returns:
            Tool result with a pretty-printed JSON array, or ``ok=False`` for
            invalid / oversized input.
        """

        document = str(invocation.arguments.get("text", ""))
        if not document.strip():
            return self._fail("document is empty", {})
        if len(document) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"document exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(document)},
            )

        mode = str(invocation.arguments.get("mode", _DEFAULT_MODE)).strip().lower()
        if mode not in _MODES:
            supported = ", ".join(sorted(_MODES))
            return self._fail(
                f"unsupported mode: {mode!r}; supported: {supported}",
                {"mode": mode},
            )

        raw_lines = document.splitlines()
        # Drop a single trailing empty line from a final newline, but keep
        # interior blank lines so we can reject or skip them explicitly.
        if raw_lines and raw_lines[-1] == "":
            raw_lines = raw_lines[:-1]

        if len(raw_lines) > _MAX_LINES:
            return self._fail(
                f"document exceeds max_lines={_MAX_LINES}",
                {"lines": len(raw_lines)},
            )

        items: list[object] = []
        for index, line in enumerate(raw_lines, start=1):
            if not line.strip():
                return self._fail(
                    f"blank line at line {index}",
                    {"line": index, "mode": mode},
                )
            try:
                value = json.loads(
                    line,
                    parse_constant=_reject_non_finite,
                    parse_float=_parse_finite_float,
                )
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                return self._fail(
                    f"invalid JSON on line {index}: {exc}",
                    {"line": index, "mode": mode},
                )
            if mode == "objects" and not isinstance(value, dict):
                return self._fail(
                    f"line {index} is not a JSON object",
                    {"line": index, "mode": mode, "type": type(value).__name__},
                )
            items.append(value)

        content = json.dumps(items, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=content,
            metadata={
                "mode": mode,
                "lines": len(items),
                "chars": len(document),
            },
        )

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
