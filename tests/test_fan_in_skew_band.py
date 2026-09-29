"""Unit tests for FanInSkewBandGuard."""

from __future__ import annotations

import pytest

from multi_bot_agentic.fan_in_skew_band import FanInSkewBandGuard


def test_balanced_band() -> None:
    """Low skew is balanced."""

    status = FanInSkewBandGuard().check("s1", fastest_s=1.0, slowest_s=1.2)
    assert status.band == "balanced"
    assert status.requires_human_review is True


def test_skewed_band() -> None:
    """Moderate skew is skewed."""

    status = FanInSkewBandGuard().check("s1", fastest_s=1.0, slowest_s=2.5)
    assert status.band == "skewed"


def test_straggler_band() -> None:
    """High skew is straggler."""

    status = FanInSkewBandGuard().check("s1", fastest_s=1.0, slowest_s=5.0)
    assert status.band == "straggler"


def test_empty_session_raises() -> None:
    """Empty session id raises ValueError."""

    with pytest.raises(ValueError, match="session_id"):
        FanInSkewBandGuard().check(" ", fastest_s=1.0, slowest_s=1.0)
