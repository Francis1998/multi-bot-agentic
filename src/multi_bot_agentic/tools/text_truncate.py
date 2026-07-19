"""Deterministic text truncation tool.

Agent runs routinely need a bounded preview of a long observation: a log tail
for a rationale trace, a clipped tool payload before the next LLM turn, or a
short summary field for the durable event log. Asking a language model to
truncate is unreliable (dropped characters, invented ellipses, inconsistent
lengths). This tool truncates text to a requested maximum length, optionally
appending an ellipsis marker when content was removed, with bounded input size
and structured failures for empty or invalid limits. It never executes code and
never makes a network request, matching the ``diff``, ``duration``, ``hash``,
``slugify``, and ``json_format`` tool contracts.

Because the decision engine only forwards a single ``text`` payload from
``TOOL:truncate:<payload>``, the max length may be supplied either as a
``max_length`` argument (tests and programmatic callers) or embedded in ``text``
via the sentinel ``<<<TRUNCATE>>>`` (for example ``document<<<TRUNCATE>>>64``).
When neither is provided, a default max length of 256 is applied.
"""

from __future__ import annotations

from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_MAX_LENGTH_CAP: Final[int] = 20_000
_DEFAULT_MAX_LENGTH: Final[int] = 256
_DEFAULT_ELLIPSIS: Final[str] = "..."
_MAX_ELLIPSIS_CHARS: Final[int] = 16
_SPLIT_SENTINEL: Final[str] = "<<<TRUNCATE>>>"


class TextTruncateTool:
    """Truncate text to a maximum length, optionally appending an ellipsis."""

    name = "truncate"
    description = "Truncates text to max_length characters (text<<<TRUNCATE>>>N, or max_length arg; optional ellipsis)."

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Truncate the document in the invocation text.

        Args:
            invocation: Tool invocation whose ``text`` argument holds the
                document (optionally split on ``<<<TRUNCATE>>>`` with a max
                length on the right), whose optional ``max_length`` argument
                sets the maximum output length, and whose optional ``ellipsis``
                argument overrides the default ``...`` marker appended when the
                document is clipped.

        Returns:
            Tool result whose ``content`` is the truncated text (and whose
            metadata reports whether clipping occurred), or ``ok=False`` and an
            explanation when the document is empty/oversized or ``max_length`` /
            ``ellipsis`` is invalid.
        """

        document, embedded_max, error = self._resolve_document(invocation.arguments)
        if error is not None:
            return self._fail(error, {})

        assert document is not None
        if not document:
            return self._fail("text is empty", {})
        if len(document) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"text exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(document)},
            )

        if "max_length" in invocation.arguments:
            max_length = self._parse_max_length(invocation.arguments.get("max_length"))
            if max_length is None:
                return self._fail(
                    f"max_length must be an integer 1..{_MAX_LENGTH_CAP}, "
                    f"got {invocation.arguments.get('max_length')!r}",
                    {"max_length": str(invocation.arguments.get("max_length"))},
                )
        elif embedded_max is not None:
            max_length = embedded_max
        else:
            max_length = _DEFAULT_MAX_LENGTH

        ellipsis = str(invocation.arguments.get("ellipsis", _DEFAULT_ELLIPSIS))
        if len(ellipsis) > _MAX_ELLIPSIS_CHARS:
            return self._fail(
                f"ellipsis exceeds max_chars={_MAX_ELLIPSIS_CHARS}",
                {"chars": len(ellipsis)},
            )

        if len(document) <= max_length:
            payload: dict[str, object] = {
                "truncated": False,
                "original_chars": len(document),
                "max_length": max_length,
            }
            return ToolResult(
                tool_name=self.name,
                ok=True,
                content=document,
                metadata=payload,
            )

        if len(ellipsis) >= max_length:
            truncated = document[:max_length]
            used_ellipsis = False
        else:
            truncated = document[: max_length - len(ellipsis)] + ellipsis
            used_ellipsis = True

        payload = {
            "truncated": True,
            "original_chars": len(document),
            "max_length": max_length,
            "ellipsis_applied": used_ellipsis,
        }
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=truncated,
            metadata=payload,
        )

    @classmethod
    def _resolve_document(cls, arguments: dict[str, object]) -> tuple[str | None, int | None, str | None]:
        """Resolve document and optional embedded max length from ``text``.

        Args:
            arguments: Tool invocation arguments.

        Returns:
            ``(document, embedded_max_length, error)``.
        """

        text = str(arguments.get("text", ""))
        if _SPLIT_SENTINEL not in text:
            return text, None, None

        document, remainder = text.split(_SPLIT_SENTINEL, maxsplit=1)
        if _SPLIT_SENTINEL in remainder:
            return None, None, "text contains more than one <<<TRUNCATE>>> sentinel"
        remainder = remainder.strip()
        parsed = cls._parse_max_length(remainder)
        if parsed is None:
            return None, None, (f"truncate sentinel value must be an integer 1..{_MAX_LENGTH_CAP}, got {remainder!r}")
        return document, parsed, None

    @staticmethod
    def _parse_max_length(value: object) -> int | None:
        """Coerce a ``max_length`` argument to an allowed positive integer.

        Args:
            value: Raw ``max_length`` argument.

        Returns:
            Length in ``1.._MAX_LENGTH_CAP``, or None when invalid.
        """

        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value if 1 <= value <= _MAX_LENGTH_CAP else None
        if isinstance(value, str):
            text = value.strip()
            if text.isdigit():
                parsed = int(text)
                return parsed if 1 <= parsed <= _MAX_LENGTH_CAP else None
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
