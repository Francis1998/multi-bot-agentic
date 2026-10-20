"""Tests for ToolTimeoutCascadeBandAdvisor."""

from __future__ import annotations

import pytest

from multi_bot_agentic.tool_timeout_cascade_band import ToolTimeoutCascadeBandAdvisor


def test_ok_band() -> None:
    """Below soft is ok."""

    status = ToolTimeoutCascadeBandAdvisor().advise("s1", cascade_ratio=0.1)
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_elevated_band() -> None:
    """Between soft and hard is elevated."""

    status = ToolTimeoutCascadeBandAdvisor(soft_limit=0.22, hard_limit=0.58).advise(
        "s1", cascade_ratio=0.39999999999999997
    )
    assert status.band == "elevated"


def test_blocked_band() -> None:
    """Above hard is blocked."""

    status = ToolTimeoutCascadeBandAdvisor(soft_limit=0.22, hard_limit=0.58).advise("s1", cascade_ratio=0.78)
    assert status.band == "blocked"


def test_invalid_session() -> None:
    """Empty session_id raises."""

    with pytest.raises(ValueError, match="session_id"):
        ToolTimeoutCascadeBandAdvisor().advise("  ", cascade_ratio=0.1)


def test_invalid_metric() -> None:
    """Negative metric raises."""

    with pytest.raises(ValueError, match="cascade_ratio"):
        ToolTimeoutCascadeBandAdvisor().advise("s1", cascade_ratio=-0.1)


def test_invalid_limits() -> None:
    """Bad ctor limits raise."""

    with pytest.raises(ValueError, match="hard_limit"):
        ToolTimeoutCascadeBandAdvisor(soft_limit=0.5, hard_limit=0.2)
