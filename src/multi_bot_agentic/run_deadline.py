"""Advisory wall-clock deadline watchdog for agent runs.

Tracks a run deadline and reports remaining/expired status via ``check``.
Never kills or terminates processes itself — callers decide how to stop.
Distinct from ``ToolCircuitBreaker`` (per-tool failure isolation) and
``AdaptiveConcurrencyLimiter`` (in-flight caps) — this is a thin,
stdlib-only wall-clock signal for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x /
Kimi K2 agent loops. Fills a gap vs AutoGen/CrewAI/LangGraph, which often
rely on step counts without an explicit wall-clock advisory.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True)
class DeadlineStatus:
    """Outcome of a deadline check.

    Attributes:
        remaining_seconds: Seconds until deadline (negative when overdue).
        expired: True when ``now >= deadline_at``.
        deadline_at: Absolute aware UTC deadline.
    """

    remaining_seconds: float
    expired: bool
    deadline_at: datetime


class RunDeadlineWatchdog:
    """Advisory wall-clock deadline for a single agent run.

    Caller-driven v1: construct with ``deadline_at`` or ``duration_seconds``,
    then poll ``check(now)``. Does not kill processes or cancel threads.
    """

    def __init__(
        self,
        *,
        deadline_at: datetime | None = None,
        duration_seconds: float | None = None,
        started_at: datetime | None = None,
    ) -> None:
        """Create a watchdog.

        Args:
            deadline_at: Absolute aware datetime deadline (exclusive with
                ``duration_seconds``).
            duration_seconds: Positive duration from ``started_at`` (or now).
            started_at: Aware start time when using ``duration_seconds``.

        Raises:
            ValueError: When args are missing, conflicting, non-positive, or
                timezone-naive.
        """

        has_deadline = deadline_at is not None
        has_duration = duration_seconds is not None
        if has_deadline == has_duration:
            raise ValueError("provide exactly one of deadline_at or duration_seconds")

        if has_deadline:
            assert deadline_at is not None
            self._require_aware(deadline_at, "deadline_at")
            self._deadline_at = deadline_at
            return

        assert duration_seconds is not None
        if duration_seconds <= 0:
            raise ValueError("duration_seconds must be > 0")
        start = started_at or datetime.now(timezone.utc)
        self._require_aware(start, "started_at")
        self._deadline_at = start + timedelta(seconds=float(duration_seconds))

    @property
    def deadline_at(self) -> datetime:
        """Absolute aware deadline."""

        return self._deadline_at

    def check(self, now: datetime | None = None) -> DeadlineStatus:
        """Return remaining/expired status for ``now``.

        Args:
            now: Aware datetime to evaluate; defaults to UTC now.

        Returns:
            DeadlineStatus with remaining_seconds and expired flag.

        Raises:
            ValueError: When ``now`` is timezone-naive.
        """

        current = now or datetime.now(timezone.utc)
        self._require_aware(current, "now")
        remaining = (self._deadline_at - current).total_seconds()
        return DeadlineStatus(
            remaining_seconds=remaining,
            expired=remaining <= 0,
            deadline_at=self._deadline_at,
        )

    @staticmethod
    def _require_aware(value: datetime, label: str) -> None:
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            raise ValueError(f"{label} must be timezone-aware")
