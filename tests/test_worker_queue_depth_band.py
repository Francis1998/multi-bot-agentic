"""Tests for WorkerQueueDepthBandAdvisor."""

from __future__ import annotations

import pytest

from multi_bot_agentic.worker_queue_depth_band import WorkerQueueDepthBandAdvisor


def test_ok() -> None:
    """Below soft limit is ok."""

    status = WorkerQueueDepthBandAdvisor(soft_limit=0.5, hard_limit=0.8).advise("s1", queue_depth_ratio=0.2)
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_elevated() -> None:
    """Between soft and hard is elevated."""

    status = WorkerQueueDepthBandAdvisor(soft_limit=0.5, hard_limit=0.8).advise("s1", queue_depth_ratio=0.6)
    assert status.band == "elevated"


def test_blocked() -> None:
    """Above hard is blocked."""

    status = WorkerQueueDepthBandAdvisor(soft_limit=0.5, hard_limit=0.8).advise("s1", queue_depth_ratio=0.9)
    assert status.band == "blocked"


def test_empty_session() -> None:
    """Empty session_id raises."""

    with pytest.raises(ValueError, match="session_id"):
        WorkerQueueDepthBandAdvisor().advise("  ", queue_depth_ratio=0.1)


def test_negative_metric() -> None:
    """Negative metric raises."""

    with pytest.raises(ValueError, match="queue_depth_ratio"):
        WorkerQueueDepthBandAdvisor().advise("s1", queue_depth_ratio=-1.0)
