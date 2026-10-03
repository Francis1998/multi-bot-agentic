"""Unit tests for ToolSandboxMemoryQuotaGuard."""

from __future__ import annotations

import pytest

from multi_bot_agentic.tool_sandbox_memory_quota import ToolSandboxMemoryQuotaGuard


def test_ok() -> None:
    """Low metric is ok."""

    status = ToolSandboxMemoryQuotaGuard().check("s1", memory_mb=256.0)
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_elevated() -> None:
    """Mid metric is elevated."""

    status = ToolSandboxMemoryQuotaGuard().check("s1", memory_mb=768.0)
    assert status.band == "elevated"


def test_blocked() -> None:
    """High metric is blocked."""

    status = ToolSandboxMemoryQuotaGuard().check("s1", memory_mb=1025.0)
    assert status.band == "blocked"


def test_invalid() -> None:
    """Negative metric raises."""

    with pytest.raises(ValueError, match="memory_mb"):
        ToolSandboxMemoryQuotaGuard().check("s1", memory_mb=-1.0)
