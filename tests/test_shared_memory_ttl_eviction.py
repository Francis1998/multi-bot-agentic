"""Unit tests for SharedMemoryTtlEvictionAdvisor."""

from __future__ import annotations

import pytest

from multi_bot_agentic.shared_memory_ttl_eviction import SharedMemoryTtlEvictionAdvisor


def test_ok() -> None:
    """Low expired ratio is ok."""

    status = SharedMemoryTtlEvictionAdvisor().advise("s1", expired_ratio=0.1)
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_elevated() -> None:
    """Mid expired ratio is elevated."""

    status = SharedMemoryTtlEvictionAdvisor().advise("s1", expired_ratio=0.35)
    assert status.band == "elevated"


def test_blocked() -> None:
    """High expired ratio is blocked."""

    status = SharedMemoryTtlEvictionAdvisor().advise("s1", expired_ratio=0.8)
    assert status.band == "blocked"


def test_invalid() -> None:
    """Out-of-range ratio raises."""

    with pytest.raises(ValueError, match="expired_ratio"):
        SharedMemoryTtlEvictionAdvisor().advise("s1", expired_ratio=1.5)
