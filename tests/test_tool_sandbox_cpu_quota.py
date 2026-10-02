"""Unit tests for ToolSandboxCpuQuotaGuard."""

from __future__ import annotations

import pytest

from multi_bot_agentic.tool_sandbox_cpu_quota import ToolSandboxCpuQuotaGuard


def test_ok() -> None:
    """Low CPU is ok."""

    status = ToolSandboxCpuQuotaGuard().check("s1", cpu_percent=40.0)
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_elevated() -> None:
    """Mid CPU is elevated."""

    status = ToolSandboxCpuQuotaGuard().check("s1", cpu_percent=80.0)
    assert status.band == "elevated"


def test_blocked() -> None:
    """High CPU is blocked."""

    status = ToolSandboxCpuQuotaGuard().check("s1", cpu_percent=99.0)
    assert status.band == "blocked"


def test_invalid() -> None:
    """Negative CPU raises."""

    with pytest.raises(ValueError, match="cpu_percent"):
        ToolSandboxCpuQuotaGuard().check("s1", cpu_percent=-1.0)
