"""Unit tests for SharedMemoryConflictBandGuard."""

from __future__ import annotations

import pytest

from multi_bot_agentic.shared_memory_conflict_band import SharedMemoryConflictBandGuard


def test_aligned_band() -> None:
    """Matching versions are aligned."""

    status = SharedMemoryConflictBandGuard().check("s1", key="plan", local_version=2, remote_version=2)
    assert status.band == "aligned"
    assert status.requires_human_review is True


def test_diverge_band() -> None:
    """Small skew is diverge."""

    status = SharedMemoryConflictBandGuard().check("s1", key="plan", local_version=2, remote_version=3)
    assert status.band == "diverge"


def test_conflict_band() -> None:
    """Large skew is conflict."""

    status = SharedMemoryConflictBandGuard().check("s1", key="plan", local_version=1, remote_version=5)
    assert status.band == "conflict"


def test_empty_key_raises() -> None:
    """Empty key raises ValueError."""

    with pytest.raises(ValueError, match="key"):
        SharedMemoryConflictBandGuard().check("s1", key=" ", local_version=0, remote_version=0)
