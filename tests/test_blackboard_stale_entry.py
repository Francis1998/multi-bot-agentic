"""Unit tests for BlackboardStaleEntryAdvisor."""

from __future__ import annotations

import pytest

from multi_bot_agentic.blackboard_stale_entry import BlackboardStaleEntryAdvisor


def test_ok() -> None:
    """Low metric is ok."""

    status = BlackboardStaleEntryAdvisor().advise("s1", stale_age_seconds=60.0)
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_elevated() -> None:
    """Mid metric is elevated."""

    status = BlackboardStaleEntryAdvisor().advise("s1", stale_age_seconds=900.0)
    assert status.band == "elevated"


def test_blocked() -> None:
    """High metric is blocked."""

    status = BlackboardStaleEntryAdvisor().advise("s1", stale_age_seconds=7200.0)
    assert status.band == "blocked"


def test_invalid() -> None:
    """Negative metric raises."""

    with pytest.raises(ValueError, match="stale_age_seconds"):
        BlackboardStaleEntryAdvisor().advise("s1", stale_age_seconds=-1.0)
