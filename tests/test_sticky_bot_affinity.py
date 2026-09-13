"""Tests for StickyBotAffinityStore."""

from __future__ import annotations

import pytest

from multi_bot_agentic.sticky_bot_affinity import StickyBotAffinityStore


def test_set_get_pin() -> None:
    """set then get returns the pinned bot for a session."""

    store = StickyBotAffinityStore()
    binding = store.set(
        "sess-1",
        "researcher",
        bound_at_iso="2026-09-13T12:00:00+00:00",
    )
    assert binding.session_id == "sess-1"
    assert binding.bot_id == "researcher"
    assert binding.bound_at_iso == "2026-09-13T12:00:00+00:00"

    got = store.get("sess-1")
    assert got is not None
    assert got.bot_id == "researcher"
    assert got.session_id == "sess-1"


def test_set_overwrites_existing() -> None:
    """Re-set for the same session replaces the bot pin."""

    store = StickyBotAffinityStore()
    store.set("sess-1", "bot-a")
    updated = store.set("sess-1", "bot-b", bound_at_iso="2026-09-13T13:00:00+00:00")
    assert updated.bot_id == "bot-b"
    assert store.get("sess-1") is not None
    assert store.get("sess-1").bot_id == "bot-b"  # type: ignore[union-attr]


def test_get_missing_returns_none() -> None:
    """Unknown session_id returns None."""

    store = StickyBotAffinityStore()
    assert store.get("missing") is None


def test_clear_removes_binding() -> None:
    """clear drops the session pin and returns True once."""

    store = StickyBotAffinityStore()
    store.set("sess-1", "bot-a")
    assert store.clear("sess-1") is True
    assert store.get("sess-1") is None
    assert store.clear("sess-1") is False


def test_sessions_are_isolated() -> None:
    """Different sessions keep independent bot pins."""

    store = StickyBotAffinityStore()
    store.set("s1", "alpha")
    store.set("s2", "beta")
    assert store.get("s1").bot_id == "alpha"  # type: ignore[union-attr]
    assert store.get("s2").bot_id == "beta"  # type: ignore[union-attr]
    store.clear("s1")
    assert store.get("s1") is None
    assert store.get("s2").bot_id == "beta"  # type: ignore[union-attr]


def test_rejects_empty_ids() -> None:
    """Empty session_id or bot_id raises ValueError."""

    store = StickyBotAffinityStore()
    with pytest.raises(ValueError, match="session_id"):
        store.set("  ", "bot")
    with pytest.raises(ValueError, match="bot_id"):
        store.set("sess", " ")
    with pytest.raises(ValueError, match="session_id"):
        store.get("")
    with pytest.raises(ValueError, match="session_id"):
        store.clear("  ")


def test_default_bound_at_iso() -> None:
    """Omitting bound_at_iso still yields a non-empty ISO-like stamp."""

    store = StickyBotAffinityStore()
    binding = store.set("sess", "bot")
    assert "T" in binding.bound_at_iso
