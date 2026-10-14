"""Unit tests for BlackboardCasWriteSkewGuard."""

from __future__ import annotations

import pytest

from multi_bot_agentic.blackboard_cas_write_skew import BlackboardCasWriteSkewGuard


def test_ok() -> None:
    """Band ok."""

    status = BlackboardCasWriteSkewGuard().advise("s1", write_skew_score=0.3000)
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_elevated() -> None:
    """Band elevated."""

    mid = (0.6 + 0.9) / 2
    status = BlackboardCasWriteSkewGuard().advise("s1", write_skew_score=mid)
    assert status.band == "elevated"


def test_blocked() -> None:
    """Band blocked."""

    status = BlackboardCasWriteSkewGuard().advise("s1", write_skew_score=1.8000)
    assert status.band == "blocked"


def test_invalid_raises() -> None:
    """Invalid metric raises ValueError."""

    with pytest.raises(ValueError, match="write_skew_score"):
        BlackboardCasWriteSkewGuard().advise("s1", write_skew_score=-1.0)
