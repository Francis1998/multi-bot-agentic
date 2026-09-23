"""Unit tests for BotIdleTimeoutEvictor."""

from __future__ import annotations

from pathlib import Path

import pytest

from multi_bot_agentic.bot_idle_timeout import BotIdleTimeoutEvictor


def test_active() -> None:
    """Low idle is active."""

    report = BotIdleTimeoutEvictor().check("bot-a", idle_seconds=10.0, timeout_seconds=100.0)
    assert report.band == "active"
    assert report.requires_human_review is True


def test_evict() -> None:
    """Idle at timeout is evict."""

    report = BotIdleTimeoutEvictor().check("bot-a", idle_seconds=300.0, timeout_seconds=300.0)
    assert report.band == "evict"


def test_idle_band() -> None:
    """Between 70% and 100% of timeout is idle."""

    report = BotIdleTimeoutEvictor().check("bot-a", idle_seconds=80.0, timeout_seconds=100.0)
    assert report.band == "idle"


def test_invalid_raises() -> None:
    """Empty bot_id raises ValueError."""

    with pytest.raises(ValueError, match="bot_id"):
        BotIdleTimeoutEvictor().check(" ", idle_seconds=1.0)


def test_no_httpx_import() -> None:
    """Module source must not import httpx."""

    src = Path(__file__).resolve().parents[1] / "src/multi_bot_agentic/bot_idle_timeout.py"
    assert "httpx" not in src.read_text(encoding="utf-8")
