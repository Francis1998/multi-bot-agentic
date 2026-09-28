"""Unit tests for ToolResultSchemaHashGate."""

from __future__ import annotations

import pytest

from multi_bot_agentic.tool_result_schema_hash import ToolResultSchemaHashGate


def test_match_band() -> None:
    """Identical hashes are match."""

    status = ToolResultSchemaHashGate().check("search", expected_hash="abc123def", observed_hash="abc123def")
    assert status.band == "match"
    assert status.requires_human_review is True


def test_near_match_band() -> None:
    """Shared 8-char prefix is near_match."""

    status = ToolResultSchemaHashGate().check("search", expected_hash="abc123dexxxx", observed_hash="abc123deyyyy")
    assert status.band == "near_match"


def test_drift_band() -> None:
    """Unrelated hashes are drift."""

    status = ToolResultSchemaHashGate().check("search", expected_hash="aaaaaaaa", observed_hash="bbbbbbbb")
    assert status.band == "drift"


def test_empty_tool_raises() -> None:
    """Empty tool name raises ValueError."""

    with pytest.raises(ValueError, match="tool_name"):
        ToolResultSchemaHashGate().check(" ", expected_hash="a", observed_hash="a")
