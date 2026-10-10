"""Unit tests for ToolSandboxDnsRebindGuard."""

from __future__ import annotations

import pytest

from multi_bot_agentic.tool_sandbox_dns_rebind import ToolSandboxDnsRebindGuard


def test_ok() -> None:
    """Band ok."""

    status = ToolSandboxDnsRebindGuard().check("s1", rebind_score=0.1)
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_elevated() -> None:
    """Band elevated."""

    status = ToolSandboxDnsRebindGuard().check("s1", rebind_score=0.4)
    assert status.band == "elevated"


def test_blocked() -> None:
    """Band blocked."""

    status = ToolSandboxDnsRebindGuard().check("s1", rebind_score=0.9)
    assert status.band == "blocked"


def test_invalid_raises() -> None:
    """Invalid metric raises ValueError."""

    with pytest.raises(ValueError, match="rebind_score"):
        ToolSandboxDnsRebindGuard().check("s1", rebind_score=-1.0)
