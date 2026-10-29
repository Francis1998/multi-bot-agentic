"""Tests for OrchestratorPriorityInversionBandAdvisor."""

from __future__ import annotations

import pytest

from multi_bot_agentic.orchestrator_priority_inversion_band import OrchestratorPriorityInversionBandAdvisor


def test_ok_band() -> None:
    """Within soft limit."""

    status = OrchestratorPriorityInversionBandAdvisor(soft_limit=0.5, hard_limit=0.8).advise("s1", inversion_ratio=0.2)
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_elevated_band() -> None:
    """Between soft and hard."""

    status = OrchestratorPriorityInversionBandAdvisor(soft_limit=0.5, hard_limit=0.8).advise("s1", inversion_ratio=0.6)
    assert status.band == "elevated"


def test_blocked_band() -> None:
    """Above hard limit."""

    status = OrchestratorPriorityInversionBandAdvisor(soft_limit=0.5, hard_limit=0.8).advise("s1", inversion_ratio=0.9)
    assert status.band == "blocked"


def test_invalid_session() -> None:
    """Empty session raises."""

    with pytest.raises(ValueError, match="session_id"):
        OrchestratorPriorityInversionBandAdvisor().advise("  ", inversion_ratio=0.1)


def test_invalid_metric() -> None:
    """Negative metric raises."""

    with pytest.raises(ValueError, match="inversion_ratio"):
        OrchestratorPriorityInversionBandAdvisor().advise("s1", inversion_ratio=-1.0)
