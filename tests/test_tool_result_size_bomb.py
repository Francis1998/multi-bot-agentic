"""Unit tests for ToolResultSizeBombGuard."""

from __future__ import annotations

import pytest

from multi_bot_agentic.tool_result_size_bomb import ToolResultSizeBombGuard


def test_ok() -> None:
    """Band ok."""

    status = ToolResultSizeBombGuard().check("s1", result_bytes=0.1)
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_elevated() -> None:
    """Band elevated."""

    status = ToolResultSizeBombGuard().check("s1", result_bytes=0.4)
    assert status.band == "elevated"


def test_blocked() -> None:
    """Band blocked."""

    status = ToolResultSizeBombGuard().check("s1", result_bytes=0.9)
    assert status.band == "blocked"


def test_invalid_raises() -> None:
    """Invalid metric raises ValueError."""

    with pytest.raises(ValueError, match="result_bytes"):
        ToolResultSizeBombGuard().check("s1", result_bytes=-1.0)
