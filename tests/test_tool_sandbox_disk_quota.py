"""Unit tests for ToolSandboxDiskQuotaGuard."""

from __future__ import annotations

import pytest

from multi_bot_agentic.tool_sandbox_disk_quota import ToolSandboxDiskQuotaGuard


def test_ok() -> None:
    """Low metric is ok."""

    status = ToolSandboxDiskQuotaGuard().check("s1", disk_mb=512.0)
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_elevated() -> None:
    """Mid metric is elevated."""

    status = ToolSandboxDiskQuotaGuard().check("s1", disk_mb=2048.0)
    assert status.band == "elevated"


def test_blocked() -> None:
    """High metric is blocked."""

    status = ToolSandboxDiskQuotaGuard().check("s1", disk_mb=5000.0)
    assert status.band == "blocked"


def test_invalid() -> None:
    """Negative metric raises."""

    with pytest.raises(ValueError, match="disk_mb"):
        ToolSandboxDiskQuotaGuard().check("s1", disk_mb=-1.0)
