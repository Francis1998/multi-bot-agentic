"""ISO-8601 duration parsing tool.

Agent runs routinely reconcile durations that arrive as ISO-8601 strings: a
retry backoff of ``PT30S``, a cache TTL of ``PT1H30M``, or a task budget of
``P1DT2H``. Comparing, summing, or scheduling against those values reliably
requires a single scalar (total seconds), and a language model cannot be trusted
to convert ``PT1H30M`` to ``5400`` arithmetically. This tool parses an ISO-8601
duration and reports its total length in seconds alongside a normalized
component breakdown. It never executes code and never makes a network request,
and it is fully deterministic: it reads no wall-clock ``now`` and applies only
fixed-length conversions.

Calendar components (years ``Y`` and months ``M`` in the date part) are refused
on purpose: they have no fixed length in seconds (a month is 28-31 days, a year
365/366 days), so converting them would silently produce an inexact result.
Weeks, days, hours, minutes, and seconds are fixed-length and fully supported,
including a fractional smallest component and an optional leading ``-`` sign.
Designators are normalised with ``str.upper`` so lowercase payloads such as
``pt1h30m`` parse the same as ``PT1H30M``. This matches the ``datetime``,
``hash``, ``base64``, ``json_format``, ``url_parse``, ``uuid5``, and ``slugify``
tool contracts.
"""

from __future__ import annotations

import json
import re
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 128
_SECONDS_PER_WEEK: Final[int] = 604_800
_SECONDS_PER_DAY: Final[int] = 86_400
_SECONDS_PER_HOUR: Final[int] = 3_600
_SECONDS_PER_MINUTE: Final[int] = 60

# Fixed-length ISO-8601 duration grammar: an optional sign, ``P``, an optional
# date part of weeks/days, and an optional ``T`` time part of hours/minutes/
# seconds. Years and months are deliberately excluded (see module docstring);
# a duration carrying them is matched separately to emit a targeted failure.
_DURATION_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^(?P<sign>-)?P"
    r"(?=\d|T)"
    r"(?:(?P<weeks>\d+(?:\.\d+)?)W)?"
    r"(?:(?P<days>\d+(?:\.\d+)?)D)?"
    r"(?:T"
    r"(?:(?P<hours>\d+(?:\.\d+)?)H)?"
    r"(?:(?P<minutes>\d+(?:\.\d+)?)M)?"
    r"(?:(?P<seconds>\d+(?:\.\d+)?)S)?"
    r")?$"
)


class DurationTool:
    """Parse an ISO-8601 duration into total seconds and a component breakdown."""

    name = "duration"
    description = "Parses an ISO-8601 duration (weeks/days/hours/minutes/seconds) into total seconds."

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Parse the ISO-8601 duration supplied in the invocation text.

        Args:
            invocation: Tool invocation whose ``text`` argument holds the
                ISO-8601 duration string (for example ``PT1H30M`` or
                ``-P1DT2H``).

        Returns:
            Tool result whose ``content`` is a canonical JSON object with the
            total seconds and the normalized component breakdown, or ``ok=False``
            and an explanation when the duration is empty, too long, carries
            unsupported calendar components, or is not a parseable ISO-8601
            duration.
        """

        document = str(invocation.arguments.get("text", "")).strip().upper()
        if not document:
            return self._fail("duration is empty", {})
        if len(document) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"duration exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(document)},
            )

        match = _DURATION_PATTERN.match(document)
        if match is None:
            if self._has_calendar_component(document):
                return self._fail(
                    "calendar components (years/months) are not supported; they have no fixed length in seconds",
                    {"duration": document},
                )
            return self._fail(
                "could not parse duration as ISO-8601",
                {"duration": document},
            )

        if self._all_components_absent(match):
            # A bare ``P``/``PT`` (no numeric component) carries no length.
            return self._fail("duration has no components", {"duration": document})

        components = self._components(match)
        total_seconds = (
            components["weeks"] * _SECONDS_PER_WEEK
            + components["days"] * _SECONDS_PER_DAY
            + components["hours"] * _SECONDS_PER_HOUR
            + components["minutes"] * _SECONDS_PER_MINUTE
            + components["seconds"]
        )
        if match.group("sign") == "-":
            total_seconds = -total_seconds

        payload: dict[str, object] = {
            "total_seconds": self._as_number(total_seconds),
            "negative": match.group("sign") == "-",
            "weeks": self._as_number(components["weeks"]),
            "days": self._as_number(components["days"]),
            "hours": self._as_number(components["hours"]),
            "minutes": self._as_number(components["minutes"]),
            "seconds": self._as_number(components["seconds"]),
        }
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False),
            metadata=payload,
        )

    @staticmethod
    def _has_calendar_component(document: str) -> bool:
        """Report whether the duration's date part carries years or months.

        The date part is everything before the ``T`` time separator (or the whole
        string when no ``T`` is present). A ``Y`` designator there is always a
        year, and an ``M`` there is a month; both are calendar components with no
        fixed length. An ``M`` after ``T`` is minutes and is not a calendar
        component.

        Args:
            document: The trimmed duration string.

        Returns:
            True when the date part contains a year or month designator.
        """

        date_part = document.split("T", 1)[0]
        return "Y" in date_part or "M" in date_part

    @classmethod
    def _all_components_absent(cls, match: re.Match[str]) -> bool:
        """Report whether the duration captured no numeric component at all.

        Args:
            match: The successful duration match.

        Returns:
            True when weeks, days, and every time component are absent.
        """

        names = ("weeks", "days", "hours", "minutes", "seconds")
        return all(match.group(name) is None for name in names)

    @staticmethod
    def _components(match: re.Match[str]) -> dict[str, float]:
        """Extract the numeric duration components, defaulting absent ones to 0.

        Args:
            match: The successful duration match.

        Returns:
            Mapping of component name to its float value.
        """

        names = ("weeks", "days", "hours", "minutes", "seconds")
        return {name: float(match.group(name)) if match.group(name) is not None else 0.0 for name in names}

    @staticmethod
    def _as_number(value: float) -> float | int:
        """Render a float without a spurious trailing ``.0`` when integral.

        Args:
            value: Numeric value.

        Returns:
            An ``int`` when the value is integral, else the ``float``.
        """

        return int(value) if float(value).is_integer() else value

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result.

        Args:
            message: Human-readable failure explanation.
            metadata: Structured metadata for the failure.

        Returns:
            A ``ok=False`` tool result carrying the message and metadata.
        """

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
