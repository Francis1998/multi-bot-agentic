"""Unit tests for ParallelToolCollisionAdvisor."""

from __future__ import annotations

import pytest

from multi_bot_agentic.parallel_tool_collision import ParallelToolCollisionAdvisor


def test_ok() -> None:
    """Band ok."""

    status = ParallelToolCollisionAdvisor().advise("s1", collision_ratio=0.3000)
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_elevated() -> None:
    """Band elevated."""

    mid = (0.6 + 0.9) / 2
    status = ParallelToolCollisionAdvisor().advise("s1", collision_ratio=mid)
    assert status.band == "elevated"


def test_blocked() -> None:
    """Band blocked."""

    status = ParallelToolCollisionAdvisor().advise("s1", collision_ratio=1.8000)
    assert status.band == "blocked"


def test_invalid_raises() -> None:
    """Invalid metric raises ValueError."""

    with pytest.raises(ValueError, match="collision_ratio"):
        ParallelToolCollisionAdvisor().advise("s1", collision_ratio=-1.0)
