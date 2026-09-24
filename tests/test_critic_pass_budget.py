"""Unit tests for CriticPassBudgetLimiter."""

from __future__ import annotations

from pathlib import Path

import pytest

from multi_bot_agentic.critic_pass_budget import CriticPassBudgetLimiter


def test_ok_band() -> None:
    """Plenty of critic passes remaining is ok."""

    status = CriticPassBudgetLimiter().check("s1", passes_used=0, max_passes=3)
    assert status.band == "ok"
    assert status.remaining == 3


def test_exhausted() -> None:
    """Used == max is exhausted."""

    status = CriticPassBudgetLimiter().check("s1", passes_used=3, max_passes=3)
    assert status.band == "exhausted"


def test_near_limit() -> None:
    """One remaining of three is near_limit."""

    status = CriticPassBudgetLimiter().check("s1", passes_used=2, max_passes=3)
    assert status.band == "near_limit"


def test_invalid_raises() -> None:
    """Empty session_id raises ValueError."""

    with pytest.raises(ValueError, match="session_id"):
        CriticPassBudgetLimiter().check(" ", passes_used=0)


def test_no_httpx_import() -> None:
    """Module source must not import httpx (CI has no httpx)."""

    src = Path(__file__).resolve().parents[1] / "src/multi_bot_agentic/critic_pass_budget.py"
    assert "httpx" not in src.read_text(encoding="utf-8")
