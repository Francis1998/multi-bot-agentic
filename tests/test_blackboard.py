"""Tests for SharedBlackboard."""

from __future__ import annotations

import pytest

from multi_bot_agentic.blackboard import BlackboardEntry, SharedBlackboard


def test_put_get_and_revision_increment() -> None:
    """put/get round-trip and revisions bump on overwrite."""

    board = SharedBlackboard()
    first = board.put("plan", "draft v1", writer_bot_id="planner")
    second = board.put("plan", "draft v2", writer_bot_id="writer")

    assert first.revision == 1
    assert second.revision == 2
    loaded = board.get("plan")
    assert loaded is not None
    assert loaded.value == "draft v2"
    assert loaded.writer_bot_id == "writer"
    assert isinstance(loaded, BlackboardEntry)


def test_put_rejects_empty_key_and_oversize_value() -> None:
    """Empty keys and oversized values raise ValueError."""

    board = SharedBlackboard(max_value_chars=8)
    with pytest.raises(ValueError, match="key must be non-empty"):
        board.put("  ", "ok")
    with pytest.raises(ValueError, match="max_value_chars"):
        board.put("k", "x" * 9)


def test_put_rejects_max_keys_on_new_key_but_allows_overwrite() -> None:
    """New keys beyond capacity fail; overwriting an existing key still works."""

    board = SharedBlackboard(max_keys=1)
    board.put("a", "1")
    with pytest.raises(ValueError, match="max_keys"):
        board.put("b", "2")
    updated = board.put("a", "1b")
    assert updated.revision == 2
    assert board.get("a") is not None
    assert board.get("b") is None


def test_delete_and_snapshot() -> None:
    """delete removes keys; snapshot returns an independent copy."""

    board = SharedBlackboard()
    board.put("x", "1")
    board.put("y", "2")
    snap = board.snapshot()
    assert set(snap) == {"x", "y"}
    snap["x"] = BlackboardEntry(key="x", value="mutated", writer_bot_id=None, revision=99)
    loaded = board.get("x")
    assert loaded is not None
    assert loaded.value == "1"
    assert board.delete("x") is True
    assert board.delete("x") is False
    assert board.get("x") is None
    assert "y" in board.snapshot()


def test_constructor_rejects_invalid_bounds() -> None:
    """Invalid constructor bounds raise ValueError."""

    with pytest.raises(ValueError, match="max_keys"):
        SharedBlackboard(max_keys=0)
    with pytest.raises(ValueError, match="max_value_chars"):
        SharedBlackboard(max_value_chars=0)
