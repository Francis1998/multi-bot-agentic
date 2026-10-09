"""Unit tests for AgentDeadlockDetectorGuard."""

from __future__ import annotations

import pytest

from multi_bot_agentic.agent_deadlock_detector import AgentDeadlockDetectorGuard


def test_ok() -> None:
    """Band ok."""

    status = AgentDeadlockDetectorGuard().check("s1", deadlock_score=0.1)
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_elevated() -> None:
    """Band elevated."""

    status = AgentDeadlockDetectorGuard().check("s1", deadlock_score=0.4)
    assert status.band == "elevated"


def test_blocked() -> None:
    """Band blocked."""

    status = AgentDeadlockDetectorGuard().check("s1", deadlock_score=0.9)
    assert status.band == "blocked"


def test_invalid_raises() -> None:
    """Invalid metric raises ValueError."""

    with pytest.raises(ValueError, match="deadlock_score"):
        AgentDeadlockDetectorGuard().check("s1", deadlock_score=-1.0)
