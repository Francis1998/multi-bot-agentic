"""Unit tests for ToolSandboxSyscallDenylistGuard."""

from __future__ import annotations

import pytest

from multi_bot_agentic.tool_sandbox_syscall_denylist import ToolSandboxSyscallDenylistGuard


def test_ok() -> None:
    """Band ok."""

    status = ToolSandboxSyscallDenylistGuard().check("s1", denied_syscall_rate=0.0250)
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_elevated() -> None:
    """Band elevated."""

    mid = (0.05 + 0.2) / 2
    status = ToolSandboxSyscallDenylistGuard().check("s1", denied_syscall_rate=mid)
    assert status.band == "elevated"


def test_blocked() -> None:
    """Band blocked."""

    status = ToolSandboxSyscallDenylistGuard().check("s1", denied_syscall_rate=0.4000)
    assert status.band == "blocked"


def test_invalid_raises() -> None:
    """Invalid metric raises ValueError."""

    with pytest.raises(ValueError, match="denied_syscall_rate"):
        ToolSandboxSyscallDenylistGuard().check("s1", denied_syscall_rate=-1.0)
