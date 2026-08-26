"""Deterministic iCalendar (.ics) VEVENT parser tool.

Agents often receive calendar invites or exported `.ics` snippets and need
structured event fields before the next LLM turn. Asking a model to parse
folded iCalendar lines can drop `DTSTART`/`UID` values or invent fields.
This tool uses only the Python standard library (no ``icalendar`` dependency),
unfolds RFC 5545 line continuations, and extracts bounded VEVENT
SUMMARY/DTSTART/DTEND/UID/LOCATION properties. It never executes code and
never makes network requests. Safe for GPT-5.5 / Claude Sonnet 4.6 /
Gemini 3.x / Kimi K2 workers.

Arguments accept a single ``text`` ICS body. Output is JSON Lines (one event
object per line) capped at 100 events.
"""

from __future__ import annotations

import json
import re
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_MAX_EVENTS: Final[int] = 100
_EVENT_FIELDS: Final[tuple[str, ...]] = ("SUMMARY", "DTSTART", "DTEND", "UID", "LOCATION")
_BEGIN_VEVENT: Final[str] = "BEGIN:VEVENT"
_END_VEVENT: Final[str] = "END:VEVENT"
_PROP_RE: Final[re.Pattern[str]] = re.compile(r"^([A-Za-z0-9-]+)(?:;[^:]*)?:(.*)$")


class IcsParseTool:
    """Parse iCalendar text and extract bounded VEVENT fields."""

    name = "ics_parse"
    description = (
        "Parses iCalendar (.ics) text and extracts VEVENT SUMMARY/DTSTART/"
        "DTEND/UID/LOCATION as JSON Lines (stdlib only; max 20_000 chars, 100 events)."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Parse VEVENT blocks from an ICS document.

        Args:
            invocation: Tool invocation whose arguments hold ``text`` (ICS body).

        Returns:
            Tool result with JSON Lines of extracted events, or ``ok=False`` when
            input is empty, oversized, or contains no VEVENT blocks.
        """

        document = str(invocation.arguments.get("text", ""))
        if not document.strip():
            return self._fail("text is empty", {})
        if len(document) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"text exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(document)},
            )

        unfolded = self._unfold_lines(document)
        events = self._extract_events(unfolded)
        if not events:
            return self._fail("ics has no VEVENT blocks", {"chars": len(document)})
        if len(events) > _MAX_EVENTS:
            return self._fail(
                f"ics exceeds max_events={_MAX_EVENTS}",
                {"events": len(events)},
            )

        lines = [json.dumps(event, ensure_ascii=False, sort_keys=True) for event in events]
        content = "\n".join(lines) + "\n"
        if len(content) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"ics output exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(content), "events": len(events)},
            )

        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=content,
            metadata={
                "events": len(events),
                "chars": len(content),
                "input_chars": len(document),
            },
        )

    @staticmethod
    def _unfold_lines(document: str) -> list[str]:
        """Unfold RFC 5545 folded lines into logical property lines."""

        normalized = document.replace("\r\n", "\n").replace("\r", "\n")
        logical: list[str] = []
        for raw_line in normalized.split("\n"):
            if logical and raw_line[:1] in {" ", "\t"}:
                logical[-1] += raw_line[1:]
            else:
                logical.append(raw_line)
        return logical

    @classmethod
    def _extract_events(cls, lines: list[str]) -> list[dict[str, str]]:
        """Extract SUMMARY/DTSTART/DTEND/UID/LOCATION from each VEVENT."""

        events: list[dict[str, str]] = []
        in_event = False
        current: dict[str, str] = {}

        for line in lines:
            stripped = line.strip()
            upper = stripped.upper()
            if upper == _BEGIN_VEVENT:
                in_event = True
                current = dict.fromkeys(_EVENT_FIELDS, "")
                continue
            if upper == _END_VEVENT:
                if in_event:
                    events.append(current)
                in_event = False
                current = {}
                continue
            if not in_event or not stripped:
                continue

            match = _PROP_RE.match(stripped)
            if match is None:
                continue
            name = match.group(1).upper()
            if name not in _EVENT_FIELDS:
                continue
            value = cls._unescape_text(match.group(2))
            # Keep the first occurrence of each field within an event.
            if not current[name]:
                current[name] = value

        return events

    @staticmethod
    def _unescape_text(value: str) -> str:
        """Unescape RFC 5545 TEXT escapes (\\\\, \\n, \\N, \\,, \\;)."""

        out: list[str] = []
        index = 0
        while index < len(value):
            char = value[index]
            if char == "\\" and index + 1 < len(value):
                nxt = value[index + 1]
                if nxt in {"n", "N"}:
                    out.append("\n")
                elif nxt in {"\\", ",", ";"}:
                    out.append(nxt)
                else:
                    out.append(nxt)
                index += 2
                continue
            out.append(char)
            index += 1
        return "".join(out)

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
