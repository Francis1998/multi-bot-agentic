"""Unit tests for SharedMemoryQuotaGuard."""

from __future__ import annotations

from pathlib import Path

import pytest

from multi_bot_agentic.shared_memory_quota import SharedMemoryQuotaGuard


def test_ok_band() -> None:
    """Plenty of writes remaining is ok."""

    status = SharedMemoryQuotaGuard().check("s1", "bot-a", writes_used=2, max_writes=20)
    assert status.band == "ok"
    assert status.remaining == 18


def test_exhausted() -> None:
    """Used == max is exhausted."""

    status = SharedMemoryQuotaGuard().check("s1", "bot-a", writes_used=20, max_writes=20)
    assert status.band == "exhausted"
    assert status.remaining == 0


def test_near_limit() -> None:
    """Few remaining writes is near_limit."""

    status = SharedMemoryQuotaGuard().check("s1", "bot-a", writes_used=19, max_writes=20)
    assert status.band == "near_limit"


def test_invalid_raises() -> None:
    """Empty bot_id raises ValueError."""

    with pytest.raises(ValueError, match="bot_id"):
        SharedMemoryQuotaGuard().check("s1", "  ", writes_used=0)


def test_no_httpx_import() -> None:
    """Module source must not import httpx (CI has no httpx)."""

    src = Path(__file__).resolve().parents[1] / "src/multi_bot_agentic/shared_memory_quota.py"
    assert "httpx" not in src.read_text(encoding="utf-8")
