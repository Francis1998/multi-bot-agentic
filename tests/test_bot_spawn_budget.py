"""Unit tests for BotSpawnBudgetLimiter."""

from __future__ import annotations

from pathlib import Path

import pytest

from multi_bot_agentic.bot_spawn_budget import BotSpawnBudgetLimiter


def test_ok_band() -> None:
    """Plenty of spawn budget remaining is ok."""

    status = BotSpawnBudgetLimiter().check("s1", bots_spawned=2, max_bots=8)
    assert status.band == "ok"
    assert status.remaining == 6


def test_exhausted() -> None:
    """Spawned == max is exhausted."""

    status = BotSpawnBudgetLimiter().check("s1", bots_spawned=8, max_bots=8)
    assert status.band == "exhausted"
    assert status.remaining == 0


def test_near_limit() -> None:
    """Few remaining spawns is near_limit."""

    status = BotSpawnBudgetLimiter().check("s1", bots_spawned=7, max_bots=8)
    assert status.band == "near_limit"
    assert status.requires_human_review is True


def test_invalid_session_raises() -> None:
    """Empty session_id raises ValueError."""

    with pytest.raises(ValueError, match="session_id"):
        BotSpawnBudgetLimiter().check(" ", bots_spawned=0)


def test_no_httpx_import() -> None:
    """Module source must not import httpx (CI has no httpx)."""

    src = Path(__file__).resolve().parents[1] / "src/multi_bot_agentic/bot_spawn_budget.py"
    assert "httpx" not in src.read_text(encoding="utf-8")
