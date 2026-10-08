"""Unit tests for AgentHandoffLatencyAdvisor."""

from __future__ import annotations

import pytest

from multi_bot_agentic.agent_handoff_latency import AgentHandoffLatencyAdvisor


def test_ok() -> None:
    """Band ok."""

    status = AgentHandoffLatencyAdvisor().advise("s1", latency_ms=0.1)
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_elevated() -> None:
    """Band elevated."""

    status = AgentHandoffLatencyAdvisor().advise("s1", latency_ms=0.4)
    assert status.band == "elevated"


def test_blocked() -> None:
    """Band blocked."""

    status = AgentHandoffLatencyAdvisor().advise("s1", latency_ms=0.9)
    assert status.band == "blocked"


def test_invalid_raises() -> None:
    """Invalid metric raises ValueError."""

    with pytest.raises(ValueError, match="latency_ms"):
        AgentHandoffLatencyAdvisor().advise("s1", latency_ms=-1.0)
