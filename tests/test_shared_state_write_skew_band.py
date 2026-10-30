"""Tests for SharedStateWriteSkewBandAdvisor."""

from __future__ import annotations

import pytest

from multi_bot_agentic.shared_state_write_skew_band import SharedStateWriteSkewBandAdvisor


def test_ok_band() -> None:
    """Within soft limit."""

    status = SharedStateWriteSkewBandAdvisor(soft_limit=0.5, hard_limit=0.8).advise("s1", write_skew_ratio=0.2)
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_elevated_band() -> None:
    """Between soft and hard."""

    status = SharedStateWriteSkewBandAdvisor(soft_limit=0.5, hard_limit=0.8).advise("s1", write_skew_ratio=0.6)
    assert status.band == "elevated"


def test_blocked_band() -> None:
    """Above hard limit."""

    status = SharedStateWriteSkewBandAdvisor(soft_limit=0.5, hard_limit=0.8).advise("s1", write_skew_ratio=0.9)
    assert status.band == "blocked"


def test_invalid_session() -> None:
    """Empty session raises."""

    with pytest.raises(ValueError, match="session_id"):
        SharedStateWriteSkewBandAdvisor().advise("  ", write_skew_ratio=0.1)


def test_invalid_metric() -> None:
    """Negative metric raises."""

    with pytest.raises(ValueError, match="write_skew_ratio"):
        SharedStateWriteSkewBandAdvisor().advise("s1", write_skew_ratio=-1.0)
