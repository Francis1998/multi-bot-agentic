"""Unit tests for ToolInvocationDeadlineGuard."""

from __future__ import annotations

import pytest

from multi_bot_agentic.tool_invocation_deadline import ToolInvocationDeadlineGuard


def test_within_budget() -> None:
    """Low ratio is within_budget."""

    status = ToolInvocationDeadlineGuard().check("s1", tool_name="search", elapsed_s=1.0, deadline_s=10.0)
    assert status.band == "within_budget"
    assert status.requires_human_review is True


def test_approaching() -> None:
    """Mid ratio is approaching."""

    status = ToolInvocationDeadlineGuard().check("s1", tool_name="search", elapsed_s=8.0, deadline_s=10.0)
    assert status.band == "approaching"


def test_expired() -> None:
    """At-or-over deadline is expired."""

    status = ToolInvocationDeadlineGuard().check("s1", tool_name="search", elapsed_s=10.0, deadline_s=10.0)
    assert status.band == "expired"


def test_empty_tool_raises() -> None:
    """Empty tool name raises ValueError."""

    with pytest.raises(ValueError, match="tool_name"):
        ToolInvocationDeadlineGuard().check("s1", tool_name=" ", elapsed_s=1.0, deadline_s=5.0)
