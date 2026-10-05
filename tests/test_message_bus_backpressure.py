"""Unit tests for MessageBusBackpressureAdvisor."""

from __future__ import annotations

import pytest

from multi_bot_agentic.message_bus_backpressure import MessageBusBackpressureAdvisor


def test_ok() -> None:
    """Low metric is ok."""

    status = MessageBusBackpressureAdvisor().advise("s1", queue_depth=50.0)
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_elevated() -> None:
    """Mid metric is elevated."""

    status = MessageBusBackpressureAdvisor().advise("s1", queue_depth=300.0)
    assert status.band == "elevated"


def test_blocked() -> None:
    """High metric is blocked."""

    status = MessageBusBackpressureAdvisor().advise("s1", queue_depth=750.0)
    assert status.band == "blocked"


def test_invalid() -> None:
    """Negative metric raises."""

    with pytest.raises(ValueError, match="queue_depth"):
        MessageBusBackpressureAdvisor().advise("s1", queue_depth=-1.0)
