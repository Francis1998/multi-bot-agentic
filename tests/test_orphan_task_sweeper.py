"""Unit tests for OrphanTaskSweeperGuard."""

from __future__ import annotations

import pytest

from multi_bot_agentic.orphan_task_sweeper import OrphanTaskSweeperGuard


def test_ok() -> None:
    """Band ok."""

    status = OrphanTaskSweeperGuard().check("s1", orphan_count=0.1)
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_elevated() -> None:
    """Band elevated."""

    status = OrphanTaskSweeperGuard().check("s1", orphan_count=0.4)
    assert status.band == "elevated"


def test_blocked() -> None:
    """Band blocked."""

    status = OrphanTaskSweeperGuard().check("s1", orphan_count=0.9)
    assert status.band == "blocked"


def test_invalid_raises() -> None:
    """Invalid metric raises ValueError."""

    with pytest.raises(ValueError, match="orphan_count"):
        OrphanTaskSweeperGuard().check("s1", orphan_count=-1.0)
