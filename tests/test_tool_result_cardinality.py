"""Unit tests for ToolResultCardinalityGate."""

from __future__ import annotations

import pytest

from multi_bot_agentic.tool_result_cardinality import ToolResultCardinalityGate


def test_ok() -> None:
    """Within soft limit is ok."""

    status = ToolResultCardinalityGate().check("s1", tool_name="search", item_count=10)
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_elevated() -> None:
    """Between soft and hard is elevated."""

    status = ToolResultCardinalityGate().check("s1", tool_name="search", item_count=250)
    assert status.band == "elevated"


def test_blocked() -> None:
    """Above hard is blocked."""

    status = ToolResultCardinalityGate().check("s1", tool_name="search", item_count=5000)
    assert status.band == "blocked"


def test_invalid_count() -> None:
    """Negative count raises."""

    with pytest.raises(ValueError, match="item_count"):
        ToolResultCardinalityGate().check("s1", tool_name="x", item_count=-1)


def test_empty_tool() -> None:
    """Empty tool raises."""

    with pytest.raises(ValueError, match="tool_name"):
        ToolResultCardinalityGate().check("s1", tool_name=" ", item_count=1)


def test_empty_session() -> None:
    """Empty session raises."""

    with pytest.raises(ValueError, match="session_id"):
        ToolResultCardinalityGate().check("", tool_name="x", item_count=1)
