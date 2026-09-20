"""Unit tests for FanInBarrierGate."""

from __future__ import annotations

from pathlib import Path

import pytest

from multi_bot_agentic.fanin_barrier import FanInBarrierGate


def test_releases_at_quorum() -> None:
    """Barrier releases once required distinct bots arrive."""

    gate = FanInBarrierGate(required=2, mode="hard")
    first = gate.arrive("join", "bot-a")
    assert first.released is False
    assert first.allowed is False
    second = gate.arrive("join", "bot-b")
    assert second.released is True
    assert second.allowed is True
    assert second.arrived == ("bot-a", "bot-b")


def test_duplicate_arrival_does_not_double_count() -> None:
    """Same bot arriving twice counts once."""

    gate = FanInBarrierGate(required=2, mode="hard")
    gate.arrive("join", "bot-a")
    again = gate.arrive("join", "bot-a")
    assert again.count == 1
    assert again.released is False


def test_advisory_allows_before_release() -> None:
    """Advisory mode allows progress before quorum."""

    gate = FanInBarrierGate(required=3, mode="advisory")
    status = gate.arrive("join", "bot-a")
    assert status.released is False
    assert status.allowed is True


def test_reset() -> None:
    """Reset clears arrivals."""

    gate = FanInBarrierGate(required=1)
    gate.arrive("join", "bot-a")
    gate.reset("join")
    assert gate.status("join").count == 0


def test_invalid_required_raises() -> None:
    """required < 1 raises ValueError."""

    with pytest.raises(ValueError, match="required"):
        FanInBarrierGate(required=0)


def test_module_has_no_httpx_import() -> None:
    """Feature module must not import httpx (offline-only)."""

    import multi_bot_agentic.fanin_barrier as feature_mod

    src = Path(feature_mod.__file__).read_text(encoding="utf-8")
    assert "httpx" not in src

