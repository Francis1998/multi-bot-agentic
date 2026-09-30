"""Unit tests for BlackboardWriteAmplificationBandGuard."""

from __future__ import annotations

import pytest

from multi_bot_agentic.blackboard_write_amplification import BlackboardWriteAmplificationBandGuard


def test_ok_band() -> None:
    """Low amplification is ok."""

    status = BlackboardWriteAmplificationBandGuard(soft_limit=2.0, hard_limit=5.0).check(
        "s1", write_count=1, read_count=4
    )
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_soft_band() -> None:
    """Soft amplification band."""

    status = BlackboardWriteAmplificationBandGuard(soft_limit=2.0, hard_limit=5.0).check(
        "s1", write_count=6, read_count=2
    )
    assert status.band == "soft"


def test_hard_band() -> None:
    """Hard amplification band."""

    status = BlackboardWriteAmplificationBandGuard(soft_limit=2.0, hard_limit=5.0).check(
        "s1", write_count=20, read_count=2
    )
    assert status.band == "hard"


def test_zero_reads_uses_unit_denominator() -> None:
    """Zero reads does not divide by zero."""

    status = BlackboardWriteAmplificationBandGuard().check("s1", write_count=3, read_count=0)
    assert status.amplification == 3.0


def test_invalid_session() -> None:
    """Empty session raises."""

    with pytest.raises(ValueError, match="session_id"):
        BlackboardWriteAmplificationBandGuard().check("  ", write_count=1, read_count=1)


def test_invalid_limits() -> None:
    """Bad ctor limits raise."""

    with pytest.raises(ValueError, match="hard_limit"):
        BlackboardWriteAmplificationBandGuard(soft_limit=3.0, hard_limit=2.0)


def test_negative_counts() -> None:
    """Negative counts raise."""

    with pytest.raises(ValueError, match="write_count"):
        BlackboardWriteAmplificationBandGuard().check("s1", write_count=-1, read_count=1)
