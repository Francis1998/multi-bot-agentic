"""Unit tests for ToolRetryBudgetBandGuard."""

from __future__ import annotations

import pytest

from multi_bot_agentic.tool_retry_budget import ToolRetryBudgetBandGuard


def test_ok() -> None:
    """Low metric is ok."""

    status = ToolRetryBudgetBandGuard().check("s1", retry_count=1.0)
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_elevated() -> None:
    """Mid metric is elevated."""

    status = ToolRetryBudgetBandGuard().check("s1", retry_count=5.0)
    assert status.band == "elevated"


def test_blocked() -> None:
    """High metric is blocked."""

    status = ToolRetryBudgetBandGuard().check("s1", retry_count=15.0)
    assert status.band == "blocked"


def test_invalid() -> None:
    """Negative metric raises."""

    with pytest.raises(ValueError, match="retry_count"):
        ToolRetryBudgetBandGuard().check("s1", retry_count=-1.0)
