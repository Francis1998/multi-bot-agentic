"""Unit tests for ToolBudgetExhaustionBandAdvisor."""

from __future__ import annotations

import pytest

from multi_bot_agentic.tool_budget_exhaustion_band import ToolBudgetExhaustionBandAdvisor


def test_ok_band() -> None:
    """Below soft limit -> ok."""

    status = ToolBudgetExhaustionBandAdvisor().advise("s1", exhaustion_ratio=0.3500)
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_elevated_band() -> None:
    """Between soft and hard -> elevated."""

    status = ToolBudgetExhaustionBandAdvisor().advise("s1", exhaustion_ratio=0.8250)
    assert status.band == "elevated"


def test_blocked_band() -> None:
    """Above hard -> blocked."""

    status = ToolBudgetExhaustionBandAdvisor().advise("s1", exhaustion_ratio=1.1500)
    assert status.band == "blocked"


def test_invalid_session() -> None:
    """Empty session_id raises."""

    with pytest.raises(ValueError, match="session_id"):
        ToolBudgetExhaustionBandAdvisor().advise("  ", exhaustion_ratio=0.1)


def test_invalid_metric() -> None:
    """Negative metric raises."""

    with pytest.raises(ValueError, match="exhaustion_ratio"):
        ToolBudgetExhaustionBandAdvisor().advise("s1", exhaustion_ratio=-0.1)
