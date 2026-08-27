"""Deterministic 5-field cron next-fire calculator.

Scheduling agents (crontab.guru-style previews, APScheduler-like planners)
often need the next UTC fire times for a classic minute/hour/dom/month/dow
expression before the next LLM turn. Asking a model to expand cron fields is
error-prone. This tool evaluates a small deterministic subset of 5-field cron
using only the Python stdlib (no ``croniter``). It never executes code and
never makes network requests. Safe for GPT-5.5 / Claude Sonnet 4.6 /
Gemini 3.x / Kimi K2 workers.
"""

from __future__ import annotations

import calendar
from datetime import datetime, timedelta, timezone
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_DEFAULT_COUNT: Final[int] = 5
_MAX_COUNT: Final[int] = 20
_MAX_EXPRESSION_CHARS: Final[int] = 128
_MAX_SEARCH_DAYS: Final[int] = 366 * 20
_FIELD_BOUNDS: Final[tuple[tuple[str, int, int], ...]] = (
    ("minute", 0, 59),
    ("hour", 0, 23),
    ("dom", 1, 31),
    ("month", 1, 12),
    ("dow", 0, 7),  # 0 and 7 both mean Sunday
)


class CronNextTool:
    """Return the next N UTC fire times for a 5-field cron expression."""

    name = "cron_next"
    description = (
        "Parses a 5-field cron expression and returns the next N UTC fire times "
        "as ISO-8601 lines (count default 5 max 20; optional from_iso)."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Compute the next cron fire times.

        Args:
            invocation: Tool invocation with ``expression`` (or ``text``),
                optional ``count``, and optional ``from_iso``.

        Returns:
            Tool result whose content is one ISO-8601 UTC timestamp per line,
            or ``ok=False`` for invalid input.
        """

        expression = str(
            invocation.arguments.get(
                "expression",
                invocation.arguments.get("text", ""),
            )
        ).strip()
        if not expression:
            return self._fail("cron expression is empty", {})
        if len(expression) > _MAX_EXPRESSION_CHARS:
            return self._fail(
                f"expression exceeds max_chars={_MAX_EXPRESSION_CHARS}",
                {"chars": len(expression)},
            )

        count, count_error = self._resolve_count(invocation.arguments.get("count", _DEFAULT_COUNT))
        if count_error is not None:
            return self._fail(count_error, {})
        assert count is not None

        start, start_error = self._resolve_start(invocation.arguments.get("from_iso"))
        if start_error is not None:
            return self._fail(start_error, {})
        assert start is not None

        fields, parse_error = self._parse_expression(expression)
        if parse_error is not None:
            return self._fail(parse_error, {"expression": expression})
        assert fields is not None

        fires, search_error = self._next_fires(fields, start, count)
        if search_error is not None:
            return self._fail(search_error, {"expression": expression, "count": count})

        lines = [dt.strftime("%Y-%m-%dT%H:%M:%SZ") for dt in fires]
        content = "\n".join(lines) + ("\n" if lines else "")
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=content,
            metadata={
                "expression": expression,
                "count": len(fires),
                "from_iso": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "fires": lines,
            },
        )

    @staticmethod
    def _resolve_count(raw: object) -> tuple[int | None, str | None]:
        """Parse and bound the requested fire count."""

        if isinstance(raw, bool) or raw is None:
            return None, f"invalid count: {raw!r}"
        if isinstance(raw, int):
            count = raw
        elif isinstance(raw, str) and raw.strip().lstrip("-").isdigit():
            count = int(raw.strip())
        else:
            return None, f"invalid count: {raw!r}"
        if count < 1:
            return None, "count must be >= 1"
        if count > _MAX_COUNT:
            return None, f"count exceeds max={_MAX_COUNT}"
        return count, None

    @staticmethod
    def _resolve_start(raw: object) -> tuple[datetime | None, str | None]:
        """Resolve the exclusive lower bound for fire times (UTC)."""

        if raw is None or str(raw).strip() == "":
            now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
            return now, None

        text = str(raw).strip()
        try:
            if text.endswith("Z"):
                parsed = datetime.fromisoformat(text[:-1] + "+00:00")
            else:
                parsed = datetime.fromisoformat(text)
        except ValueError:
            return None, f"invalid from_iso: {text!r}"

        parsed = parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
        return parsed.replace(second=0, microsecond=0), None

    @classmethod
    def _parse_expression(
        cls,
        expression: str,
    ) -> tuple[
        tuple[frozenset[int], frozenset[int], frozenset[int], frozenset[int], frozenset[int]] | None, str | None
    ]:
        """Parse a classic 5-field cron expression into value sets."""

        parts = expression.split()
        if len(parts) != 5:
            return None, "cron expression must have exactly 5 fields (minute hour dom month dow)"

        parsed: list[frozenset[int]] = []
        for (name, lo, hi), part in zip(_FIELD_BOUNDS, parts, strict=True):
            values, error = cls._parse_field(part, lo, hi, name)
            if error is not None:
                return None, error
            assert values is not None
            parsed.append(values)

        minute, hour, dom, month, dow = parsed
        # Normalize Sunday: accept both 0 and 7, store as 0..6
        dow_norm = frozenset(0 if value == 7 else value for value in dow)
        return (minute, hour, dom, month, dow_norm), None

    @classmethod
    def _parse_field(
        cls,
        part: str,
        lo: int,
        hi: int,
        name: str,
    ) -> tuple[frozenset[int] | None, str | None]:
        """Parse one cron field into a frozenset of allowed integers."""

        if not part:
            return None, f"invalid {name} field: empty"
        values: set[int] = set()
        for token in part.split(","):
            token_values, error = cls._parse_token(token, lo, hi, name)
            if error is not None:
                return None, error
            assert token_values is not None
            values.update(token_values)
        if not values:
            return None, f"invalid {name} field: {part!r}"
        return frozenset(values), None

    @classmethod
    def _parse_token(
        cls,
        token: str,
        lo: int,
        hi: int,
        name: str,
    ) -> tuple[set[int] | None, str | None]:
        """Parse a single list item: ``*``, ``n``, ``a-b``, or ``*/step`` forms."""

        if not token:
            return None, f"invalid {name} field token: empty"

        step = 1
        body = token
        if "/" in token:
            body, step_text = token.split("/", maxsplit=1)
            if not step_text or not step_text.isdigit():
                return None, f"invalid {name} step: {token!r}"
            step = int(step_text)
            if step < 1:
                return None, f"invalid {name} step: {token!r}"

        if body == "*":
            start, end = lo, hi
        elif "-" in body:
            left, right = body.split("-", maxsplit=1)
            if not left.isdigit() or not right.isdigit():
                return None, f"invalid {name} range: {token!r}"
            start, end = int(left), int(right)
            if start > end or start < lo or end > hi:
                return None, f"invalid {name} range: {token!r}"
        else:
            if not body.isdigit():
                return None, f"invalid {name} value: {token!r}"
            start = end = int(body)
            if start < lo or start > hi:
                return None, f"invalid {name} value: {token!r}"

        # For dow, hi is 7; include 7 only when explicitly in range or as value.
        return set(range(start, end + 1, step)), None

    @classmethod
    def _next_fires(
        cls,
        fields: tuple[frozenset[int], frozenset[int], frozenset[int], frozenset[int], frozenset[int]],
        start: datetime,
        count: int,
    ) -> tuple[list[datetime], str | None]:
        """Walk forward minute-by-minute until ``count`` matching fires are found."""

        minutes, hours, doms, months, dows = fields
        cursor = start + timedelta(minutes=1)
        cursor = cursor.replace(second=0, microsecond=0)
        deadline = start + timedelta(days=_MAX_SEARCH_DAYS)
        fires: list[datetime] = []
        dom_star = doms == frozenset(range(1, 32))
        dow_star = dows == frozenset(range(0, 7))

        while cursor <= deadline and len(fires) < count:
            if (
                cursor.month in months
                and cursor.hour in hours
                and cursor.minute in minutes
                and cls._dom_dow_matches(cursor, doms, dows, dom_star, dow_star)
            ):
                fires.append(cursor)
            cursor += timedelta(minutes=1)

        if len(fires) < count:
            return [], f"could not find {count} fire times within {_MAX_SEARCH_DAYS} days"
        return fires, None

    @staticmethod
    def _dom_dow_matches(
        cursor: datetime,
        doms: frozenset[int],
        dows: frozenset[int],
        dom_star: bool,
        dow_star: bool,
    ) -> bool:
        """Apply Vixie-style DOM/DOW matching (OR when both are restricted)."""

        last_day = calendar.monthrange(cursor.year, cursor.month)[1]
        if cursor.day > last_day:
            return False

        # Python: Monday=0..Sunday=6 → cron: Sunday=0..Saturday=6
        cron_dow = (cursor.weekday() + 1) % 7
        dom_ok = cursor.day in doms
        dow_ok = cron_dow in dows

        if dom_star and dow_star:
            return True
        if dom_star:
            return dow_ok
        if dow_star:
            return dom_ok
        return dom_ok or dow_ok

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
