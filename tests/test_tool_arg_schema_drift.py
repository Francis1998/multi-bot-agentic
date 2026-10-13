"""Unit tests for ToolArgSchemaDriftGuard."""

from __future__ import annotations

import pytest

from multi_bot_agentic.tool_arg_schema_drift import ToolArgSchemaDriftGuard


def test_ok() -> None:
    """Band ok."""

    status = ToolArgSchemaDriftGuard().check("s1", schema_drift_score=0.0750)
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_elevated() -> None:
    """Band elevated."""

    mid = (0.15 + 0.4) / 2
    status = ToolArgSchemaDriftGuard().check("s1", schema_drift_score=mid)
    assert status.band == "elevated"


def test_blocked() -> None:
    """Band blocked."""

    status = ToolArgSchemaDriftGuard().check("s1", schema_drift_score=0.8000)
    assert status.band == "blocked"


def test_invalid_raises() -> None:
    """Invalid metric raises ValueError."""

    with pytest.raises(ValueError, match="schema_drift_score"):
        ToolArgSchemaDriftGuard().check("s1", schema_drift_score=-1.0)
