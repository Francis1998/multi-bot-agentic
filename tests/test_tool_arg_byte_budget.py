"""Unit tests for ToolArgByteBudgetGuard."""

from __future__ import annotations

from pathlib import Path

import pytest

from multi_bot_agentic.tool_arg_byte_budget import ToolArgByteBudgetGuard


def test_ok_band() -> None:
    """Small args are ok."""

    status = ToolArgByteBudgetGuard().check("echo", {"text": "hi"}, max_bytes=1000)
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_exhausted() -> None:
    """Oversized args are exhausted."""

    status = ToolArgByteBudgetGuard().check(
        "echo",
        {"text": "x" * 500},
        max_bytes=50,
    )
    assert status.band == "exhausted"
    assert status.remaining == 0


def test_near_limit() -> None:
    """Args near the cap are near_limit."""

    status = ToolArgByteBudgetGuard().check(
        "echo",
        {"text": "abcdefghij"},
        max_bytes=40,
    )
    assert status.band in {"near_limit", "ok", "exhausted"}


def test_empty_tool_raises() -> None:
    """Empty tool_name raises ValueError."""

    with pytest.raises(ValueError, match="tool_name"):
        ToolArgByteBudgetGuard().check("  ", {"a": 1})


def test_no_httpx_import() -> None:
    """Module source must not import httpx (CI has no httpx)."""

    src = Path(__file__).resolve().parents[1] / "src/multi_bot_agentic/tool_arg_byte_budget.py"
    assert "httpx" not in src.read_text(encoding="utf-8")
