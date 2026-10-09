"""Unit tests for ToolSandboxNetworkExfilGuard."""

from __future__ import annotations

import pytest

from multi_bot_agentic.tool_sandbox_network_exfil import ToolSandboxNetworkExfilGuard


def test_ok() -> None:
    """Band ok."""

    status = ToolSandboxNetworkExfilGuard().check("s1", exfil_score=0.1)
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_elevated() -> None:
    """Band elevated."""

    status = ToolSandboxNetworkExfilGuard().check("s1", exfil_score=0.4)
    assert status.band == "elevated"


def test_blocked() -> None:
    """Band blocked."""

    status = ToolSandboxNetworkExfilGuard().check("s1", exfil_score=0.9)
    assert status.band == "blocked"


def test_invalid_raises() -> None:
    """Invalid metric raises ValueError."""

    with pytest.raises(ValueError, match="exfil_score"):
        ToolSandboxNetworkExfilGuard().check("s1", exfil_score=-1.0)
