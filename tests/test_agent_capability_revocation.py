"""Unit tests for AgentCapabilityRevocationBandAdvisor."""

from __future__ import annotations

import pytest

from multi_bot_agentic.agent_capability_revocation import AgentCapabilityRevocationBandAdvisor


def test_ok() -> None:
    """Band ok."""

    status = AgentCapabilityRevocationBandAdvisor().advise("s1", revocation_score=0.1)
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_elevated() -> None:
    """Band elevated."""

    status = AgentCapabilityRevocationBandAdvisor().advise("s1", revocation_score=0.4)
    assert status.band == "elevated"


def test_blocked() -> None:
    """Band blocked."""

    status = AgentCapabilityRevocationBandAdvisor().advise("s1", revocation_score=0.9)
    assert status.band == "blocked"


def test_invalid_raises() -> None:
    """Invalid metric raises ValueError."""

    with pytest.raises(ValueError, match="revocation_score"):
        AgentCapabilityRevocationBandAdvisor().advise("s1", revocation_score=-1.0)
