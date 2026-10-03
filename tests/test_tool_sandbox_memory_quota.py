"""Unit tests for ToolSandboxMemoryQuotaGuard."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from multi_bot_agentic.tool_sandbox_memory_quota import ToolSandboxMemoryQuotaGuard


def test_ok_band() -> None:
    """Band ok under soft limit."""

    status = ToolSandboxMemoryQuotaGuard().check("s1", memory_mb=256.0)
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_elevated_band() -> None:
    """Band elevated between soft and hard."""

    status = ToolSandboxMemoryQuotaGuard().check("s1", memory_mb=768.0)
    assert status.band == "elevated"


def test_blocked_band() -> None:
    """Band blocked above hard limit."""

    status = ToolSandboxMemoryQuotaGuard().check("s1", memory_mb=1025.0)
    assert status.band == "blocked"


def test_invalid_id_raises() -> None:
    """Empty id raises ValueError."""

    with pytest.raises(ValueError, match="session_id"):
        ToolSandboxMemoryQuotaGuard().check("  ", memory_mb=256.0)


def test_no_network_calls() -> None:
    """Guard never performs HTTP calls."""

    with (
        patch("httpx.Client", MagicMock()) as client_cls,
        patch("httpx.AsyncClient", MagicMock()) as async_cls,
        patch("httpx.get", MagicMock()) as get_fn,
        patch("httpx.post", MagicMock()) as post_fn,
    ):
        ToolSandboxMemoryQuotaGuard().check("s1", memory_mb=768.0)
        client_cls.assert_not_called()
        async_cls.assert_not_called()
        get_fn.assert_not_called()
        post_fn.assert_not_called()
