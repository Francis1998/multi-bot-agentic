"""Tests for RunDeadlineWatchdog."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from multi_bot_agentic.run_deadline import RunDeadlineWatchdog


def test_check_remaining_before_deadline() -> None:
    """check(now) before deadline reports remaining > 0 and not expired."""

    deadline = datetime(2026, 9, 13, 12, 0, 0, tzinfo=timezone.utc)
    watchdog = RunDeadlineWatchdog(deadline_at=deadline)
    now = deadline - timedelta(seconds=30)
    status = watchdog.check(now)
    assert status.expired is False
    assert status.remaining_seconds == pytest.approx(30.0)
    assert status.deadline_at == deadline


def test_check_expired_at_or_after_deadline() -> None:
    """check(now) at/after deadline reports expired with remaining <= 0."""

    deadline = datetime(2026, 9, 13, 12, 0, 0, tzinfo=timezone.utc)
    watchdog = RunDeadlineWatchdog(deadline_at=deadline)
    status = watchdog.check(deadline)
    assert status.expired is True
    assert status.remaining_seconds == pytest.approx(0.0)

    later = deadline + timedelta(seconds=5)
    overdue = watchdog.check(later)
    assert overdue.expired is True
    assert overdue.remaining_seconds == pytest.approx(-5.0)


def test_from_duration_seconds() -> None:
    """Constructing with duration_seconds sets deadline relative to started_at."""

    started = datetime(2026, 9, 13, 10, 0, 0, tzinfo=timezone.utc)
    watchdog = RunDeadlineWatchdog(duration_seconds=60.0, started_at=started)
    mid = started + timedelta(seconds=20)
    status = watchdog.check(mid)
    assert status.expired is False
    assert status.remaining_seconds == pytest.approx(40.0)
    assert status.deadline_at == started + timedelta(seconds=60)


def test_advisory_never_kills() -> None:
    """Watchdog only signals; it has no kill/terminate API."""

    deadline = datetime(2026, 9, 13, 12, 0, 0, tzinfo=timezone.utc)
    watchdog = RunDeadlineWatchdog(deadline_at=deadline)
    assert not hasattr(watchdog, "kill")
    assert not hasattr(watchdog, "terminate")
    assert callable(watchdog.check)


def test_rejects_naive_deadline() -> None:
    """Naive (tz-less) deadline_at raises ValueError."""

    with pytest.raises(ValueError, match="timezone"):
        RunDeadlineWatchdog(deadline_at=datetime(2026, 9, 13, 12, 0, 0))


def test_rejects_invalid_duration() -> None:
    """Non-positive duration_seconds raises ValueError."""

    started = datetime(2026, 9, 13, 10, 0, 0, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="duration_seconds"):
        RunDeadlineWatchdog(duration_seconds=0, started_at=started)
    with pytest.raises(ValueError, match="duration_seconds"):
        RunDeadlineWatchdog(duration_seconds=-1, started_at=started)


def test_requires_deadline_or_duration() -> None:
    """Must supply exactly one of deadline_at or duration_seconds."""

    with pytest.raises(ValueError, match=r"deadline_at|duration_seconds"):
        RunDeadlineWatchdog()
    deadline = datetime(2026, 9, 13, 12, 0, 0, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match=r"deadline_at|duration_seconds"):
        RunDeadlineWatchdog(deadline_at=deadline, duration_seconds=10.0)


def test_check_rejects_naive_now() -> None:
    """Naive now raises ValueError."""

    deadline = datetime(2026, 9, 13, 12, 0, 0, tzinfo=timezone.utc)
    watchdog = RunDeadlineWatchdog(deadline_at=deadline)
    with pytest.raises(ValueError, match="timezone"):
        watchdog.check(datetime(2026, 9, 13, 11, 0, 0))
