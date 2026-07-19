"""Deterministic regex extraction tool.

Agent runs routinely need to pull structured fragments out of free-form text: an
error code from a log line, a ticket id from a commit message, or a capture
group from a tool payload. Asking a language model to invent matches is
unreliable (missed hits, hallucinated groups, inconsistent offsets). This tool
compiles a Python regular expression and returns every match as canonical JSON,
with bounded document/pattern size and a capped match count. It never executes
code and never makes a network request, matching the ``diff``, ``duration``,
``hash``, ``slugify``, and ``json_format`` tool contracts.

Because the decision engine only forwards a single ``text`` payload from
``TOOL:regex:<payload>``, the document and pattern may be supplied either as
separate ``text`` / ``pattern`` arguments (tests and programmatic callers) or as
a single ``text`` value split on the sentinel ``<<<REGEX>>>``.
"""

from __future__ import annotations

import json
import re
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_MAX_PATTERN_CHARS: Final[int] = 512
_MAX_MATCHES: Final[int] = 100
_SPLIT_SENTINEL: Final[str] = "<<<REGEX>>>"


class RegexExtractTool:
    """Extract regex matches from a text document as canonical JSON."""

    name = "regex"
    description = "Extracts regex matches from text (text+pattern, or text split on <<<REGEX>>>); returns JSON."

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Extract matches for the pattern against the document.

        Args:
            invocation: Tool invocation whose ``text`` and optional ``pattern``
                arguments hold the document and regex (or ``text`` alone split
                on ``<<<REGEX>>>``).

        Returns:
            Tool result whose ``content`` is canonical JSON listing each match
            (span, full match, and groups), or ``ok=False`` and an explanation
            when a side is missing/empty/oversized, the split is ambiguous, the
            pattern is invalid, or the match count exceeds the cap.
        """

        document, pattern, error = self._resolve_sides(invocation.arguments)
        if error is not None:
            return self._fail(error, {})

        assert document is not None and pattern is not None
        if len(document) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"document exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(document)},
            )
        if len(pattern) > _MAX_PATTERN_CHARS:
            return self._fail(
                f"pattern exceeds max_chars={_MAX_PATTERN_CHARS}",
                {"chars": len(pattern)},
            )

        try:
            compiled = re.compile(pattern)
        except re.error as exc:
            return self._fail(f"invalid regex: {exc}", {"pattern": pattern})

        matches: list[dict[str, object]] = []
        for match in compiled.finditer(document):
            if len(matches) >= _MAX_MATCHES:
                return self._fail(
                    f"match count exceeds max_matches={_MAX_MATCHES}",
                    {"matches": len(matches) + 1},
                )
            groups = [group if group is not None else None for group in match.groups()]
            matches.append(
                {
                    "match": match.group(0),
                    "start": match.start(),
                    "end": match.end(),
                    "groups": groups,
                }
            )

        payload: dict[str, object] = {
            "count": len(matches),
            "matches": matches,
            "pattern": pattern,
        }
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False),
            metadata={"count": len(matches), "pattern": pattern},
        )

    @classmethod
    def _resolve_sides(cls, arguments: dict[str, object]) -> tuple[str | None, str | None, str | None]:
        """Resolve document/pattern from ``text``/``pattern`` or the split sentinel.

        Args:
            arguments: Tool invocation arguments.

        Returns:
            ``(document, pattern, error)`` — exactly one of the sides-pair or the
            error string is populated.
        """

        text = str(arguments.get("text", ""))
        if "pattern" in arguments:
            pattern = str(arguments.get("pattern", ""))
            if not text:
                return None, None, "document is empty"
            if not pattern:
                return None, None, "pattern is empty"
            return text, pattern, None

        if _SPLIT_SENTINEL not in text:
            return None, None, (f"regex requires text+pattern arguments, or a single text split on {_SPLIT_SENTINEL!r}")
        document, pattern = text.split(_SPLIT_SENTINEL, maxsplit=1)
        if _SPLIT_SENTINEL in pattern:
            return None, None, "text contains more than one <<<REGEX>>> sentinel"
        document = document.strip("\n")
        pattern = pattern.strip("\n").strip()
        if not document:
            return None, None, "document is empty"
        if not pattern:
            return None, None, "pattern is empty"
        return document, pattern, None

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result.

        Args:
            message: Human-readable failure explanation.
            metadata: Structured metadata for the failure.

        Returns:
            A ``ok=False`` tool result carrying the message and metadata.
        """

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
