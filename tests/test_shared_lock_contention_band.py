"""Unit tests for SharedLockContentionBandAdvisor."""

from __future__ import annotations

import pytest

from multi_bot_agentic.shared_lock_contention_band import SharedLockContentionBandAdvisor


def test_ok_band() -> None:
    """Below soft limit -> ok."""

    status = SharedLockContentionBandAdvisor().advise("s1", contention_ratio=0.1)
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_elevated_band() -> None:
    """Between soft and hard -> elevated."""

    status = SharedLockContentionBandAdvisor().advise("s1", contention_ratio=0.4)
    assert status.band == "elevated"


def test_blocked_band() -> None:
    """Above hard -> blocked."""

    status = SharedLockContentionBandAdvisor().advise("s1", contention_ratio=0.9)
    assert status.band == "blocked"


def test_invalid_session() -> None:
    """Empty session_id raises."""

    with pytest.raises(ValueError, match="session_id"):
        SharedLockContentionBandAdvisor().advise("  ", contention_ratio=0.1)


def test_invalid_metric() -> None:
    """Negative metric raises."""

    with pytest.raises(ValueError, match="contention_ratio"):
        SharedLockContentionBandAdvisor().advise("s1", contention_ratio=-0.1)
