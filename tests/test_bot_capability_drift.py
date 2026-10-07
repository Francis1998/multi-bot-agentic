"""Unit tests for BotCapabilityDriftAdvisor."""

from __future__ import annotations

import pytest

from multi_bot_agentic.bot_capability_drift import BotCapabilityDriftAdvisor


def test_ok() -> None:
    """Low metric is ok."""

    status = BotCapabilityDriftAdvisor().advise("s1", drift_ratio=0.1)
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_elevated() -> None:
    """Mid metric is elevated."""

    status = BotCapabilityDriftAdvisor().advise("s1", drift_ratio=0.4)
    assert status.band == "elevated"


def test_blocked() -> None:
    """High metric is blocked."""

    status = BotCapabilityDriftAdvisor().advise("s1", drift_ratio=0.9)
    assert status.band == "blocked"


def test_invalid() -> None:
    """Negative metric raises."""

    with pytest.raises(ValueError, match="drift_ratio"):
        BotCapabilityDriftAdvisor().advise("s1", drift_ratio=-1.0)
