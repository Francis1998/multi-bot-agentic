"""Unit tests for CriticLatencySloBandGuard."""

from __future__ import annotations

import pytest

from multi_bot_agentic.critic_latency_slo import CriticLatencySloBandGuard


def test_ok() -> None:
    """Low metric is ok."""

    status = CriticLatencySloBandGuard().check("s1", latency_ms=750.0)
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_elevated() -> None:
    """Mid metric is elevated."""

    status = CriticLatencySloBandGuard().check("s1", latency_ms=2250.0)
    assert status.band == "elevated"


def test_blocked() -> None:
    """High metric is blocked."""

    status = CriticLatencySloBandGuard().check("s1", latency_ms=3001.0)
    assert status.band == "blocked"


def test_invalid() -> None:
    """Negative metric raises."""

    with pytest.raises(ValueError, match="latency_ms"):
        CriticLatencySloBandGuard().check("s1", latency_ms=-1.0)
