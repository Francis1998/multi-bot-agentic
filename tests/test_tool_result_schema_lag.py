"""Unit tests for ToolResultSchemaLagAdvisor."""

from __future__ import annotations

import pytest

from multi_bot_agentic.tool_result_schema_lag import ToolResultSchemaLagAdvisor


def test_ok() -> None:
    """Band ok."""

    status = ToolResultSchemaLagAdvisor().advise("s1", lag_ratio=0.3000)
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_elevated() -> None:
    """Band elevated."""

    mid = (0.6 + 0.9) / 2
    status = ToolResultSchemaLagAdvisor().advise("s1", lag_ratio=mid)
    assert status.band == "elevated"


def test_blocked() -> None:
    """Band blocked."""

    status = ToolResultSchemaLagAdvisor().advise("s1", lag_ratio=1.8000)
    assert status.band == "blocked"


def test_invalid_raises() -> None:
    """Invalid metric raises ValueError."""

    with pytest.raises(ValueError, match="lag_ratio"):
        ToolResultSchemaLagAdvisor().advise("s1", lag_ratio=-1.0)
