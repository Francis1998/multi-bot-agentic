"""Tests for SessionTtlExpirer."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from multi_bot_agentic.session_ttl import SessionTtlExpirer

UTC = timezone.utc


def test_touch_resets_deadline() -> None:
    """touch records activity and resets remaining toward full TTL."""

    expirer = SessionTtlExpirer(ttl_seconds=60.0, mode="advisory")
    t0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    s0 = expirer.touch("sess", now=t0)
    assert s0.remaining_seconds == 60.0
    assert s0.expired is False
    t1 = t0 + timedelta(seconds=30)
    mid = expirer.check("sess", now=t1)
    assert mid.remaining_seconds == pytest.approx(30.0)
    t2 = t0 + timedelta(seconds=40)
    refreshed = expirer.touch("sess", now=t2)
    assert refreshed.remaining_seconds == 60.0
    assert refreshed.last_activity_at == t2


def test_check_reports_expired_without_touch() -> None:
    """check flips expired after TTL elapses without further activity."""

    expirer = SessionTtlExpirer(ttl_seconds=10.0)
    t0 = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
    expirer.touch("s", now=t0)
    later = expirer.check("s", now=t0 + timedelta(seconds=10))
    assert later.expired is True
    assert later.remaining_seconds == pytest.approx(0.0)


def test_sessions_are_isolated() -> None:
    """Different sessions keep independent activity clocks."""

    expirer = SessionTtlExpirer(ttl_seconds=5.0)
    t0 = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
    expirer.touch("a", now=t0)
    assert expirer.check("b", now=t0).last_activity_at is None
    assert expirer.check("a", now=t0 + timedelta(seconds=6)).expired is True
    assert expirer.check("b", now=t0 + timedelta(seconds=6)).expired is False


def test_hard_mode_check_raises_when_expired() -> None:
    """hard mode check raises RuntimeError once expired."""

    expirer = SessionTtlExpirer(ttl_seconds=5.0, mode="hard")
    t0 = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
    expirer.touch("sess", now=t0)
    with pytest.raises(RuntimeError, match="session TTL expired"):
        expirer.check("sess", now=t0 + timedelta(seconds=5))


def test_hard_mode_touch_raises_when_expired() -> None:
    """hard mode touch does not revive an expired session."""

    expirer = SessionTtlExpirer(ttl_seconds=5.0, mode="hard")
    t0 = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
    expirer.touch("sess", now=t0)
    with pytest.raises(RuntimeError, match="session TTL expired"):
        expirer.touch("sess", now=t0 + timedelta(seconds=6))


def test_advisory_mode_allows_check_and_touch_when_expired() -> None:
    """advisory mode reports expired without raising and allows re-touch."""

    expirer = SessionTtlExpirer(ttl_seconds=5.0, mode="advisory")
    t0 = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
    expirer.touch("sess", now=t0)
    expired = expirer.check("sess", now=t0 + timedelta(seconds=6))
    assert expired.expired is True
    revived = expirer.touch("sess", now=t0 + timedelta(seconds=7))
    assert revived.expired is False
    assert revived.remaining_seconds == 5.0


def test_reset_clears_session() -> None:
    """reset drops activity so the session can start fresh."""

    expirer = SessionTtlExpirer(ttl_seconds=5.0, mode="hard")
    t0 = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
    expirer.touch("sess", now=t0)
    assert expirer.reset("sess") is True
    assert expirer.check("sess", now=t0 + timedelta(seconds=10)).expired is False
    assert expirer.reset("sess") is False
    # After reset, hard mode accepts a new touch even after former expiry window.
    assert expirer.touch("sess", now=t0 + timedelta(seconds=11)).remaining_seconds == 5.0


def test_constructor_and_input_validation() -> None:
    """Bad bounds, empty session_id, and naive now raise ValueError."""

    with pytest.raises(ValueError, match="ttl_seconds"):
        SessionTtlExpirer(ttl_seconds=0)
    with pytest.raises(ValueError, match="mode"):
        SessionTtlExpirer(ttl_seconds=1.0, mode="soft")
    expirer = SessionTtlExpirer(ttl_seconds=1.0)
    with pytest.raises(ValueError, match="session_id"):
        expirer.touch("  ")
    with pytest.raises(ValueError, match="timezone-aware"):
        expirer.touch("s", now=datetime(2026, 1, 1, 0, 0, 0))
