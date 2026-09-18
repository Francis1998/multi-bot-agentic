"""Tests for HitlEscalationCooldownGate."""

from __future__ import annotations

import pytest

from multi_bot_agentic.hitl_escalation_cooldown import HitlEscalationCooldownGate


def test_deny_starts_cooldown() -> None:
    """record_deny starts a cooling_down window."""

    gate = HitlEscalationCooldownGate(cooldown_seconds=10.0, mode="advisory")
    status = gate.record_deny("sess:tool", now=100.0)
    assert status.cooling_down is True
    assert status.remaining_seconds == 10.0
    assert status.deny_count == 1
    assert status.allowed is True  # advisory


def test_hard_mode_blocks_while_cooling() -> None:
    """Hard mode sets allowed=False while cooling down."""

    gate = HitlEscalationCooldownGate(cooldown_seconds=5.0, mode="hard")
    gate.record_deny("k1", now=50.0)
    mid = gate.check("k1", now=52.0)
    assert mid.cooling_down is True
    assert mid.allowed is False
    done = gate.check("k1", now=56.0)
    assert done.cooling_down is False
    assert done.allowed is True


def test_reset_clears() -> None:
    """reset clears cooldown state."""

    gate = HitlEscalationCooldownGate(cooldown_seconds=3.0)
    gate.record_deny("k", now=1.0)
    assert gate.reset("k") is True
    status = gate.check("k", now=1.5)
    assert status.deny_count == 0
    assert status.cooling_down is False


def test_empty_key_raises() -> None:
    """Empty key raises ValueError."""

    with pytest.raises(ValueError, match="key"):
        HitlEscalationCooldownGate(cooldown_seconds=1.0).check("  ")
