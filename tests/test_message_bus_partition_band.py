"""Unit tests for MessageBusPartitionBandAdvisor."""

from __future__ import annotations

import pytest

from multi_bot_agentic.message_bus_partition_band import MessageBusPartitionBandAdvisor


def test_ok_band() -> None:
    """Below soft limit -> ok."""

    status = MessageBusPartitionBandAdvisor().advise("s1", partition_ratio=0.3500)
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_elevated_band() -> None:
    """Between soft and hard -> elevated."""

    status = MessageBusPartitionBandAdvisor().advise("s1", partition_ratio=0.8250)
    assert status.band == "elevated"


def test_blocked_band() -> None:
    """Above hard -> blocked."""

    status = MessageBusPartitionBandAdvisor().advise("s1", partition_ratio=1.1500)
    assert status.band == "blocked"


def test_invalid_session() -> None:
    """Empty session_id raises."""

    with pytest.raises(ValueError, match="session_id"):
        MessageBusPartitionBandAdvisor().advise("  ", partition_ratio=0.1)


def test_invalid_metric() -> None:
    """Negative metric raises."""

    with pytest.raises(ValueError, match="partition_ratio"):
        MessageBusPartitionBandAdvisor().advise("s1", partition_ratio=-0.1)
