"""Unit tests for OrchestratorStallWatchdog."""

from __future__ import annotations

import pytest

from multi_bot_agentic.orchestrator_stall_watchdog import OrchestratorStallWatchdog


def test_healthy_band() -> None:
    """Recent progress is healthy."""

    status = OrchestratorStallWatchdog().check("s1", seconds_since_progress=5.0)
    assert status.band == "healthy"
    assert status.requires_human_review is True


def test_warning_band() -> None:
    """Mid idle is warning."""

    status = OrchestratorStallWatchdog().check("s1", seconds_since_progress=45.0)
    assert status.band == "warning"


def test_stalled_band() -> None:
    """Long idle is stalled."""

    status = OrchestratorStallWatchdog().check("s1", seconds_since_progress=200.0)
    assert status.band == "stalled"


def test_empty_session_raises() -> None:
    """Empty session id raises ValueError."""

    with pytest.raises(ValueError, match="session_id"):
        OrchestratorStallWatchdog().check(" ", seconds_since_progress=1.0)
