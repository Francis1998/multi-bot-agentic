"""Unit tests for DebateRoundLimiter."""

from __future__ import annotations

from pathlib import Path

import pytest

from multi_bot_agentic.debate_round_limiter import DebateRoundLimiter


def test_ok_band() -> None:
    """Plenty of rounds remaining is ok."""

    status = DebateRoundLimiter().check("s1", rounds_used=1, max_rounds=5)
    assert status.band == "ok"
    assert status.remaining == 4
    assert status.requires_human_review is True


def test_exhausted() -> None:
    """Used == max is exhausted."""

    status = DebateRoundLimiter().check("s1", rounds_used=5, max_rounds=5)
    assert status.band == "exhausted"
    assert status.remaining == 0


def test_near_limit() -> None:
    """One remaining of five is near_limit."""

    status = DebateRoundLimiter().check("s1", rounds_used=4, max_rounds=5)
    assert status.band == "near_limit"


def test_invalid_raises() -> None:
    """Empty session_id raises ValueError."""

    with pytest.raises(ValueError, match="session_id"):
        DebateRoundLimiter().check("  ", rounds_used=0)


def test_no_httpx_import() -> None:
    """Module source must not import httpx (CI has no httpx)."""

    src = Path(__file__).resolve().parents[1] / "src/multi_bot_agentic/debate_round_limiter.py"
    assert "httpx" not in src.read_text(encoding="utf-8")
