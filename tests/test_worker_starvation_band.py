"""Tests for WorkerStarvationBandAdvisor."""

from __future__ import annotations

import pytest

from multi_bot_agentic.worker_starvation_band import WorkerStarvationBandAdvisor


def test_ok_band() -> None:
    """Below soft is ok."""

    status = WorkerStarvationBandAdvisor().advise("s1", starvation_ratio=0.1)
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_elevated_band() -> None:
    """Between soft and hard is elevated."""

    status = WorkerStarvationBandAdvisor(soft_limit=0.2, hard_limit=0.5).advise("s1", starvation_ratio=0.3)
    assert status.band == "elevated"


def test_blocked_band() -> None:
    """Above hard is blocked."""

    status = WorkerStarvationBandAdvisor(soft_limit=0.2, hard_limit=0.5).advise("s1", starvation_ratio=0.9)
    assert status.band == "blocked"


def test_invalid_session() -> None:
    """Empty session_id raises."""

    with pytest.raises(ValueError, match="session_id"):
        WorkerStarvationBandAdvisor().advise("  ", starvation_ratio=0.1)


def test_invalid_metric() -> None:
    """Negative metric raises."""

    with pytest.raises(ValueError, match="starvation_ratio"):
        WorkerStarvationBandAdvisor().advise("s1", starvation_ratio=-0.1)


def test_invalid_limits() -> None:
    """Bad ctor limits raise."""

    with pytest.raises(ValueError, match="hard_limit"):
        WorkerStarvationBandAdvisor(soft_limit=0.5, hard_limit=0.2)
