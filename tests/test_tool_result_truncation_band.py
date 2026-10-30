"""Tests for ToolResultTruncationBandAdvisor."""

from __future__ import annotations

import pytest

from multi_bot_agentic.tool_result_truncation_band import ToolResultTruncationBandAdvisor


def test_ok_band() -> None:
    """Within soft limit."""

    status = ToolResultTruncationBandAdvisor(soft_limit=0.5, hard_limit=0.8).advise("s1", truncation_ratio=0.2)
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_elevated_band() -> None:
    """Between soft and hard."""

    status = ToolResultTruncationBandAdvisor(soft_limit=0.5, hard_limit=0.8).advise("s1", truncation_ratio=0.6)
    assert status.band == "elevated"


def test_blocked_band() -> None:
    """Above hard limit."""

    status = ToolResultTruncationBandAdvisor(soft_limit=0.5, hard_limit=0.8).advise("s1", truncation_ratio=0.9)
    assert status.band == "blocked"


def test_invalid_session() -> None:
    """Empty session raises."""

    with pytest.raises(ValueError, match="session_id"):
        ToolResultTruncationBandAdvisor().advise("  ", truncation_ratio=0.1)


def test_invalid_metric() -> None:
    """Negative metric raises."""

    with pytest.raises(ValueError, match="truncation_ratio"):
        ToolResultTruncationBandAdvisor().advise("s1", truncation_ratio=-1.0)
