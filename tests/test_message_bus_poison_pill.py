"""Unit tests for MessageBusPoisonPillGuard."""

from __future__ import annotations

import pytest

from multi_bot_agentic.message_bus_poison_pill import MessageBusPoisonPillGuard


def test_ok() -> None:
    """Band ok."""

    status = MessageBusPoisonPillGuard().check("s1", poison_score=0.1)
    assert status.band == "ok"
    assert status.requires_human_review is True


def test_elevated() -> None:
    """Band elevated."""

    status = MessageBusPoisonPillGuard().check("s1", poison_score=0.4)
    assert status.band == "elevated"


def test_blocked() -> None:
    """Band blocked."""

    status = MessageBusPoisonPillGuard().check("s1", poison_score=0.9)
    assert status.band == "blocked"


def test_invalid_raises() -> None:
    """Invalid metric raises ValueError."""

    with pytest.raises(ValueError, match="poison_score"):
        MessageBusPoisonPillGuard().check("s1", poison_score=-1.0)
