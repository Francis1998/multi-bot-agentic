"""Unit tests for ToolSandboxEgressClassGuard."""

from __future__ import annotations

import pytest

from multi_bot_agentic.tool_sandbox_egress import ToolSandboxEgressClassGuard


def test_allowed() -> None:
    """Local under local max is allowed."""

    status = ToolSandboxEgressClassGuard(max_allowed="local").check("s1", tool_name="read_file", egress_class="local")
    assert status.band == "allowed"
    assert status.requires_human_review is True


def test_elevated() -> None:
    """Network under local max is elevated."""

    status = ToolSandboxEgressClassGuard(max_allowed="local").check("s1", tool_name="fetch", egress_class="network")
    assert status.band == "elevated"


def test_blocked() -> None:
    """Admin under local max is blocked."""

    status = ToolSandboxEgressClassGuard(max_allowed="local").check("s1", tool_name="shell", egress_class="admin")
    assert status.band == "blocked"


def test_invalid_class() -> None:
    """Bad egress class raises."""

    with pytest.raises(ValueError, match="egress_class"):
        ToolSandboxEgressClassGuard().check("s1", tool_name="x", egress_class="planet")


def test_invalid_max() -> None:
    """Bad max_allowed raises."""

    with pytest.raises(ValueError, match="max_allowed"):
        ToolSandboxEgressClassGuard(max_allowed="weird")


def test_empty_tool() -> None:
    """Empty tool raises."""

    with pytest.raises(ValueError, match="tool_name"):
        ToolSandboxEgressClassGuard().check("s1", tool_name=" ", egress_class="none")


def test_empty_session() -> None:
    """Empty session raises."""

    with pytest.raises(ValueError, match="session_id"):
        ToolSandboxEgressClassGuard().check("", tool_name="x", egress_class="none")
