"""ISO-8601 timestamp normalization tool.

Agent runs routinely reconcile timestamps that arrive in inconsistent shapes:
one upstream system returns ``2026-07-14T13:04:33Z``, another
``2026-07-14T15:04:33+02:00``, and a third a naive ``2026-07-14 13:04:33``.
Comparing, sorting, or logging those values reliably requires a single canonical
representation, and a language model cannot be trusted to convert time zones
arithmetically. This tool parses an ISO-8601 timestamp and re-emits it in a
canonical UTC form (``YYYY-MM-DDTHH:MM:SS+00:00``), reporting the Unix epoch and
weekday alongside it. It never executes code and never makes a network request,
and it is fully deterministic: it reads no wall-clock ``now``. It returns a
structured failure for empty or oversized input, a timestamp it cannot parse, or
a naive timestamp when the caller has not opted in to interpreting it as UTC —
matching the ``hash``, ``base64``, ``json_format``, ``url_parse``, ``uuid5``,
and ``slugify`` tool contracts.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 128
_TRUTHY: Final[frozenset[str]] = frozenset({"1", "true", "yes", "on"})
_FALSY: Final[frozenset[str]] = frozenset({"0", "false", "no", "off"})
_WEEKDAYS: Final[tuple[str, ...]] = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)


class DateTimeTool:
    """Normalize an ISO-8601 timestamp to a canonical UTC representation."""

    name = "datetime"
    description = "Normalizes an ISO-8601 timestamp to canonical UTC (optional assume_utc for naive input)."

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Normalize the ISO-8601 timestamp supplied in the invocation text.

        Args:
            invocation: Tool invocation whose ``text`` argument holds the
                ISO-8601 timestamp and whose optional ``assume_utc`` argument
                (boolean-like) opts in to interpreting a naive timestamp as UTC
                instead of failing.

        Returns:
            Tool result whose ``content`` is a canonical JSON object with the
            normalized UTC timestamp, Unix epoch seconds, and weekday, or
            ``ok=False`` and an explanation when the document is empty, too long,
            unparseable, or naive without ``assume_utc``.
        """

        document = str(invocation.arguments.get("text", "")).strip()
        if not document:
            return self._fail("timestamp is empty", {})
        if len(document) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"timestamp exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(document)},
            )

        assume_utc = self._parse_bool(invocation.arguments.get("assume_utc"))
        if assume_utc is None and "assume_utc" in invocation.arguments:
            return self._fail(
                f"assume_utc must be a boolean, got {invocation.arguments.get('assume_utc')!r}",
                {"assume_utc": str(invocation.arguments.get("assume_utc"))},
            )

        parsed = self._parse_iso8601(document)
        if parsed is None:
            return self._fail(
                "could not parse timestamp as ISO-8601",
                {"timestamp": document},
            )

        naive = parsed.tzinfo is None
        if naive and not assume_utc:
            return self._fail(
                "timestamp is naive (no timezone); pass assume_utc=true to interpret it as UTC",
                {"timestamp": document},
            )
        if naive:
            parsed = parsed.replace(tzinfo=timezone.utc)

        utc = parsed.astimezone(timezone.utc)
        components: dict[str, object] = {
            "utc": utc.isoformat(),
            "epoch_seconds": int(utc.timestamp()),
            "weekday": _WEEKDAYS[utc.weekday()],
            "assumed_utc": naive,
        }
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=json.dumps(components, indent=2, sort_keys=True, ensure_ascii=False),
            metadata=components,
        )

    @staticmethod
    def _parse_iso8601(document: str) -> datetime | None:
        """Parse an ISO-8601 timestamp string into a ``datetime``.

        A trailing ``Z``/``z`` (Zulu) designator is normalized to ``+00:00``
        before parsing so the value is accepted on every supported Python
        version, not only those whose :meth:`datetime.fromisoformat` learned to
        read ``Z`` directly.

        Args:
            document: The trimmed ISO-8601 timestamp text.

        Returns:
            The parsed ``datetime`` (aware or naive), or None when the value is
            not a parseable ISO-8601 timestamp.
        """

        candidate = document
        if candidate[-1:] in ("Z", "z"):
            candidate = f"{candidate[:-1]}+00:00"
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            return None

    @staticmethod
    def _parse_bool(value: object) -> bool | None:
        """Coerce a boolean-like ``assume_utc`` argument to a bool.

        Args:
            value: Raw argument value (may be absent, bool, or string).

        Returns:
            The boolean value, or None when absent or not boolean-like.
        """

        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            text = value.strip().lower()
            if text in _TRUTHY:
                return True
            if text in _FALSY:
                return False
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
