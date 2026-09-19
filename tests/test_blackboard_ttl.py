"""Tests for BlackboardEntryTtlEvictor."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from multi_bot_agentic.blackboard_ttl import BlackboardEntryTtlEvictor


def test_touch_then_fresh() -> None:
    """Freshly touched keys are not expired."""

    ev = BlackboardEntryTtlEvictor(ttl_seconds=60)
    now = datetime(2026, 9, 19, tzinfo=timezone.utc)
    status = ev.touch("alpha", now=now)
    assert status.expired is False
    assert status.age_seconds == 0
    assert ev.expired_keys(now=now) == ()


def test_evict_expired() -> None:
    """Keys past TTL are listed and removed by evict_expired."""

    ev = BlackboardEntryTtlEvictor(ttl_seconds=10)
    t0 = datetime(2026, 9, 19, tzinfo=timezone.utc)
    ev.touch("a", now=t0)
    ev.touch("b", now=t0 + timedelta(seconds=1))
    later = t0 + timedelta(seconds=15)
    assert ev.expired_keys(now=later) == ("a", "b")
    removed = ev.evict_expired(now=later)
    assert removed == ("a", "b")
    assert ev.expired_keys(now=later) == ()


def test_partial_expiry() -> None:
    """Only aged keys expire."""

    ev = BlackboardEntryTtlEvictor(ttl_seconds=10)
    t0 = datetime(2026, 9, 19, tzinfo=timezone.utc)
    ev.touch("old", now=t0)
    ev.touch("new", now=t0 + timedelta(seconds=8))
    mid = t0 + timedelta(seconds=11)
    assert ev.expired_keys(now=mid) == ("old",)


def test_invalid_ttl_raises() -> None:
    """Non-positive TTL raises ValueError."""

    with pytest.raises(ValueError, match="ttl_seconds"):
        BlackboardEntryTtlEvictor(ttl_seconds=0)


def test_unknown_status_raises() -> None:
    """Status on unknown key raises ValueError."""

    with pytest.raises(ValueError, match="unknown key"):
        BlackboardEntryTtlEvictor().status("missing")
