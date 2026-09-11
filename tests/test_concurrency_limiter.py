"""Tests for AdaptiveConcurrencyLimiter."""

from __future__ import annotations

import threading
import time

import pytest

from multi_bot_agentic.concurrency_limiter import AdaptiveConcurrencyLimiter


def test_rejects_invalid_bounds() -> None:
    """Constructor validates max/min in-flight bounds."""

    with pytest.raises(ValueError, match="max_in_flight"):
        AdaptiveConcurrencyLimiter(0)
    with pytest.raises(ValueError, match="min_in_flight"):
        AdaptiveConcurrencyLimiter(4, min_in_flight=0)
    with pytest.raises(ValueError, match="min_in_flight must be <="):
        AdaptiveConcurrencyLimiter(2, min_in_flight=3)


def test_acquire_release_caps_in_flight() -> None:
    """Non-blocking acquire fails when at the effective limit."""

    limiter = AdaptiveConcurrencyLimiter(2, adaptive=False)
    assert limiter.acquire(blocking=False) is True
    assert limiter.acquire(blocking=False) is True
    assert limiter.acquire(blocking=False) is False
    snap = limiter.snapshot()
    assert snap.in_flight == 2
    assert snap.effective_limit == 2
    assert snap.error_streak == 0
    limiter.release(success=True)
    assert limiter.snapshot().in_flight == 1
    assert limiter.acquire(blocking=False) is True


def test_adaptive_shrink_on_errors() -> None:
    """Unsuccessful releases shrink effective_limit toward min_in_flight."""

    limiter = AdaptiveConcurrencyLimiter(4, min_in_flight=1, adaptive=True)
    assert limiter.acquire(blocking=False) is True
    limiter.release(success=False)
    snap = limiter.snapshot()
    assert snap.effective_limit == 3
    assert snap.error_streak == 1
    assert snap.in_flight == 0

    assert limiter.acquire(blocking=False) is True
    limiter.release(success=False)
    assert limiter.snapshot().effective_limit == 2
    assert limiter.snapshot().error_streak == 2

    assert limiter.acquire(blocking=False) is True
    limiter.release(success=False)
    assert limiter.acquire(blocking=False) is True
    limiter.release(success=False)
    assert limiter.snapshot().effective_limit == 1
    assert limiter.snapshot().error_streak == 4

    # Floor: further errors do not go below min_in_flight.
    assert limiter.acquire(blocking=False) is True
    limiter.release(success=False)
    assert limiter.snapshot().effective_limit == 1


def test_recover_on_successes() -> None:
    """Successful releases clear the streak and grow the effective limit."""

    limiter = AdaptiveConcurrencyLimiter(3, min_in_flight=1, adaptive=True)
    for _ in range(2):
        assert limiter.acquire(blocking=False) is True
        limiter.release(success=False)
    assert limiter.snapshot().effective_limit == 1
    assert limiter.snapshot().error_streak == 2

    assert limiter.acquire(blocking=False) is True
    limiter.release(success=True)
    snap = limiter.snapshot()
    assert snap.error_streak == 0
    assert snap.effective_limit == 2

    assert limiter.acquire(blocking=False) is True
    limiter.release(success=True)
    assert limiter.snapshot().effective_limit == 3

    # Ceiling: further successes stay at max_in_flight.
    assert limiter.acquire(blocking=False) is True
    limiter.release(success=True)
    assert limiter.snapshot().effective_limit == 3


def test_non_adaptive_ignores_errors() -> None:
    """When adaptive=False, errors track streak but do not shrink the limit."""

    limiter = AdaptiveConcurrencyLimiter(3, min_in_flight=1, adaptive=False)
    assert limiter.acquire(blocking=False) is True
    limiter.release(success=False)
    snap = limiter.snapshot()
    assert snap.effective_limit == 3
    assert snap.error_streak == 1


def test_release_without_acquire_raises() -> None:
    """Releasing with nothing in flight raises RuntimeError."""

    limiter = AdaptiveConcurrencyLimiter(1)
    with pytest.raises(RuntimeError, match="nothing in flight"):
        limiter.release(success=True)


def test_blocking_acquire_waits_for_release() -> None:
    """Blocking acquire unblocks when another thread releases a slot."""

    limiter = AdaptiveConcurrencyLimiter(1, adaptive=False)
    assert limiter.acquire(blocking=False) is True
    released = threading.Event()

    def _release_later() -> None:
        time.sleep(0.05)
        limiter.release(success=True)
        released.set()

    thread = threading.Thread(target=_release_later)
    thread.start()
    assert limiter.acquire(blocking=True, timeout=1.0) is True
    thread.join(timeout=1.0)
    assert released.is_set()
    limiter.release(success=True)


def test_acquire_timeout_returns_false() -> None:
    """Blocking acquire with a short timeout returns False when full."""

    limiter = AdaptiveConcurrencyLimiter(1, adaptive=False)
    assert limiter.acquire(blocking=False) is True
    assert limiter.acquire(blocking=True, timeout=0.05) is False
    limiter.release(success=True)
