"""Unit tests for BlackboardReadStalenessAdvisor."""

from __future__ import annotations

import pytest

from multi_bot_agentic.blackboard_read_staleness import BlackboardReadStalenessAdvisor


def test_ok_band() -> None:
    """Below soft limit -> ok."""

    status = BlackboardReadStalenessAdvisor().advise("s1", staleness_ratio=0.1)
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_elevated_band() -> None:
    """Between soft and hard -> elevated."""

    status = BlackboardReadStalenessAdvisor().advise("s1", staleness_ratio=0.4)
    assert status.band == "elevated"


def test_blocked_band() -> None:
    """Above hard -> blocked."""

    status = BlackboardReadStalenessAdvisor().advise("s1", staleness_ratio=0.9)
    assert status.band == "blocked"


def test_invalid_session() -> None:
    """Empty session_id raises."""

    with pytest.raises(ValueError, match="session_id"):
        BlackboardReadStalenessAdvisor().advise("  ", staleness_ratio=0.1)


def test_invalid_metric() -> None:
    """Negative metric raises."""

    with pytest.raises(ValueError, match="staleness_ratio"):
        BlackboardReadStalenessAdvisor().advise("s1", staleness_ratio=-0.1)
