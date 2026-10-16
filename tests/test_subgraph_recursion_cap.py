"""Unit tests for SubgraphRecursionCapAdvisor."""

from __future__ import annotations

import pytest

from multi_bot_agentic.subgraph_recursion_cap import SubgraphRecursionCapAdvisor


def test_ok() -> None:
    """Band ok."""

    status = SubgraphRecursionCapAdvisor().advise("s1", recursion_depth_ratio=0.3000)
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_elevated() -> None:
    """Band elevated."""

    mid = (0.6 + 0.9) / 2
    status = SubgraphRecursionCapAdvisor().advise("s1", recursion_depth_ratio=mid)
    assert status.band == "elevated"


def test_blocked() -> None:
    """Band blocked."""

    status = SubgraphRecursionCapAdvisor().advise("s1", recursion_depth_ratio=1.8000)
    assert status.band == "blocked"


def test_invalid_raises() -> None:
    """Invalid metric raises ValueError."""

    with pytest.raises(ValueError, match="recursion_depth_ratio"):
        SubgraphRecursionCapAdvisor().advise("s1", recursion_depth_ratio=-1.0)
