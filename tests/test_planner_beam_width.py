"""Unit tests for PlannerBeamWidthLimiter."""

from __future__ import annotations

import pytest

from multi_bot_agentic.planner_beam_width import PlannerBeamWidthLimiter


def test_ok() -> None:
    """Within soft limit is ok."""

    status = PlannerBeamWidthLimiter().check("s1", beam_width=3)
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_elevated() -> None:
    """Between soft and hard is elevated."""

    status = PlannerBeamWidthLimiter().check("s1", beam_width=6)
    assert status.band == "elevated"


def test_blocked() -> None:
    """Above hard is blocked."""

    status = PlannerBeamWidthLimiter().check("s1", beam_width=12)
    assert status.band == "blocked"


def test_invalid_beam() -> None:
    """Non-positive beam raises."""

    with pytest.raises(ValueError, match="beam_width"):
        PlannerBeamWidthLimiter().check("s1", beam_width=0)


def test_invalid_limits() -> None:
    """Bad hard/soft raises."""

    with pytest.raises(ValueError, match="hard_limit"):
        PlannerBeamWidthLimiter(soft_limit=4, hard_limit=2)


def test_empty_session() -> None:
    """Empty session raises."""

    with pytest.raises(ValueError, match="session_id"):
        PlannerBeamWidthLimiter().check(" ", beam_width=2)
