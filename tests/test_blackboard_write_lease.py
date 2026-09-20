"""Unit tests for SharedBlackboardWriteLease."""

from __future__ import annotations

from pathlib import Path

from datetime import datetime, timedelta, timezone
import pytest

from multi_bot_agentic.blackboard_write_lease import SharedBlackboardWriteLease


def test_acquire_and_conflict_hard() -> None:
    """Second bot cannot acquire under hard mode."""

    lease = SharedBlackboardWriteLease(lease_seconds=10.0, mode="hard")
    now = datetime(2026, 9, 20, tzinfo=timezone.utc)
    first = lease.acquire("plan", "bot-a", now=now)
    assert first.acquired is True
    second = lease.acquire("plan", "bot-b", now=now)
    assert second.acquired is False
    assert second.allowed is False
    assert second.holder == "bot-a"


def test_expire_then_reacquire() -> None:
    """Expired lease can be reacquired by another bot."""

    lease = SharedBlackboardWriteLease(lease_seconds=5.0, mode="hard")
    t0 = datetime(2026, 9, 20, tzinfo=timezone.utc)
    lease.acquire("plan", "bot-a", now=t0)
    later = t0 + timedelta(seconds=6)
    status = lease.acquire("plan", "bot-b", now=later)
    assert status.acquired is True
    assert status.holder == "bot-b"
    assert status.expired is True


def test_advisory_allows_conflict() -> None:
    """Advisory mode keeps allowed=True on conflict."""

    lease = SharedBlackboardWriteLease(lease_seconds=10.0, mode="advisory")
    now = datetime(2026, 9, 20, tzinfo=timezone.utc)
    lease.acquire("k", "a", now=now)
    status = lease.acquire("k", "b", now=now)
    assert status.acquired is False
    assert status.allowed is True


def test_release() -> None:
    """Holder can release the lease."""

    lease = SharedBlackboardWriteLease(lease_seconds=10.0)
    now = datetime(2026, 9, 20, tzinfo=timezone.utc)
    lease.acquire("k", "a", now=now)
    assert lease.release("k", "a") is True
    assert lease.release("k", "a") is False


def test_invalid_mode_raises() -> None:
    """Invalid mode raises ValueError."""

    with pytest.raises(ValueError, match="mode"):
        SharedBlackboardWriteLease(mode="soft")


def test_module_has_no_httpx_import() -> None:
    """Feature module must not import httpx (offline-only)."""

    import multi_bot_agentic.blackboard_write_lease as feature_mod

    src = Path(feature_mod.__file__).read_text(encoding="utf-8")
    assert "httpx" not in src

