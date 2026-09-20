"""Unit tests for BotHeartbeatLivenessWatchdog."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from multi_bot_agentic.bot_heartbeat import BotHeartbeatLivenessWatchdog


def test_heartbeat_alive() -> None:
    """Fresh heartbeat is alive."""

    dog = BotHeartbeatLivenessWatchdog(timeout_seconds=10.0)
    now = datetime(2026, 9, 20, tzinfo=timezone.utc)
    status = dog.heartbeat("s1", "bot-a", now=now)
    assert status.band == "alive"
    assert status.stale is False


def test_stale_after_timeout() -> None:
    """Status becomes stale after timeout."""

    dog = BotHeartbeatLivenessWatchdog(timeout_seconds=5.0)
    t0 = datetime(2026, 9, 20, tzinfo=timezone.utc)
    dog.heartbeat("s1", "bot-a", now=t0)
    later = t0 + timedelta(seconds=6)
    status = dog.status("s1", "bot-a", now=later)
    assert status.band == "stale"
    assert status.stale is True
    assert dog.stale_bots("s1", now=later) == ("bot-a",)


def test_unknown_without_heartbeat() -> None:
    """Missing heartbeat is unknown/stale."""

    dog = BotHeartbeatLivenessWatchdog(timeout_seconds=5.0)
    status = dog.status("s1", "bot-x")
    assert status.band == "unknown"
    assert status.stale is True


def test_invalid_timeout_raises() -> None:
    """Non-positive timeout raises ValueError."""

    with pytest.raises(ValueError, match="timeout_seconds"):
        BotHeartbeatLivenessWatchdog(timeout_seconds=0)


def test_no_network_calls() -> None:
    """Watchdog never performs HTTP calls."""

    with (
        patch("httpx.Client", MagicMock()) as client_cls,
        patch("httpx.AsyncClient", MagicMock()) as async_cls,
    ):
        dog = BotHeartbeatLivenessWatchdog(timeout_seconds=1.0)
        dog.heartbeat("s", "b")
        client_cls.assert_not_called()
        async_cls.assert_not_called()
