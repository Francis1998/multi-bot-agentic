"""Unit tests for AgentHandoffDepthLimiter."""

from __future__ import annotations

import pytest

from multi_bot_agentic.agent_handoff_depth import AgentHandoffDepthLimiter


def test_ok_band() -> None:
    """Shallow handoff depth is ok."""

    status = AgentHandoffDepthLimiter().check("s1", handoff_depth=1, max_depth=4)
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_near_limit_band() -> None:
    """Depth near max is near_limit."""

    status = AgentHandoffDepthLimiter().check("s1", handoff_depth=3, max_depth=4)
    assert status.band == "near_limit"
    assert status.remaining == 1


def test_exhausted_band() -> None:
    """Depth at max is exhausted."""

    status = AgentHandoffDepthLimiter().check("s1", handoff_depth=4, max_depth=4)
    assert status.band == "exhausted"
    assert status.remaining == 0


def test_empty_session_raises() -> None:
    """Empty session id raises ValueError."""

    with pytest.raises(ValueError, match="session_id"):
        AgentHandoffDepthLimiter().check("  ", handoff_depth=0)
