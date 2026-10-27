"""Unit tests for OrchestratorFanInStallBandAdvisor."""

from __future__ import annotations

import pytest

from multi_bot_agentic.orchestrator_fan_in_stall_band import OrchestratorFanInStallBandAdvisor


def test_ok_band() -> None:
    """Below soft limit -> ok."""

    status = OrchestratorFanInStallBandAdvisor().advise("s1", stall_ratio=0.1500)
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_elevated_band() -> None:
    """Between soft and hard -> elevated."""

    status = OrchestratorFanInStallBandAdvisor().advise("s1", stall_ratio=0.5000)
    assert status.band == "elevated"


def test_blocked_band() -> None:
    """Above hard -> blocked."""

    status = OrchestratorFanInStallBandAdvisor().advise("s1", stall_ratio=0.9000)
    assert status.band == "blocked"


def test_invalid_session() -> None:
    """Empty session_id raises."""

    with pytest.raises(ValueError, match="session_id"):
        OrchestratorFanInStallBandAdvisor().advise("  ", stall_ratio=0.1)


def test_invalid_metric() -> None:
    """Negative metric raises."""

    with pytest.raises(ValueError, match="stall_ratio"):
        OrchestratorFanInStallBandAdvisor().advise("s1", stall_ratio=-0.1)
