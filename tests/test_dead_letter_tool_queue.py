"""Tests for DeadLetterToolQueue."""

from __future__ import annotations

import pytest

from multi_bot_agentic.dead_letter_tool_queue import DeadLetterToolQueue


def test_enqueue_list_and_acknowledge() -> None:
    """enqueue → list_pending → acknowledge removes from pending."""

    queue = DeadLetterToolQueue()
    item = queue.enqueue(
        "search",
        {"q": "docs"},
        "timeout after retries",
        3,
        enqueued_at_iso="2026-09-12T12:00:00+00:00",
    )
    assert item.tool_name == "search"
    assert item.args == {"q": "docs"}
    assert item.error == "timeout after retries"
    assert item.attempt_count == 3
    assert item.acknowledged is False
    assert item.item_id

    pending = queue.list_pending()
    assert len(pending) == 1
    assert pending[0].item_id == item.item_id

    ack = queue.acknowledge(item.item_id)
    assert ack.acknowledged is True
    assert queue.list_pending() == []


def test_args_copied() -> None:
    """Mutating caller args after enqueue does not change the stored item."""

    queue = DeadLetterToolQueue()
    args = {"path": "/tmp/x"}
    item = queue.enqueue("read", args, "not found", 2)
    args["path"] = "/tmp/y"
    assert item.args["path"] == "/tmp/x"


def test_multiple_pending_preserve_order() -> None:
    """list_pending returns items in enqueue order."""

    queue = DeadLetterToolQueue()
    a = queue.enqueue("t1", {}, "e1", 1)
    b = queue.enqueue("t2", {}, "e2", 2)
    pending = queue.list_pending()
    assert [i.item_id for i in pending] == [a.item_id, b.item_id]


def test_acknowledge_unknown_raises() -> None:
    """Unknown item_id raises KeyError."""

    queue = DeadLetterToolQueue()
    with pytest.raises(KeyError):
        queue.acknowledge("missing-id")


def test_double_acknowledge_raises() -> None:
    """Acknowledging twice raises ValueError."""

    queue = DeadLetterToolQueue()
    item = queue.enqueue("t", {}, "err", 1)
    queue.acknowledge(item.item_id)
    with pytest.raises(ValueError, match="already acknowledged"):
        queue.acknowledge(item.item_id)


def test_rejects_invalid_enqueue() -> None:
    """Empty tool/error or attempt_count < 1 raise ValueError."""

    queue = DeadLetterToolQueue()
    with pytest.raises(ValueError, match="tool_name"):
        queue.enqueue("  ", {}, "err", 1)
    with pytest.raises(ValueError, match="error"):
        queue.enqueue("t", {}, " ", 1)
    with pytest.raises(ValueError, match="attempt_count"):
        queue.enqueue("t", {}, "err", 0)
    with pytest.raises(TypeError):
        queue.enqueue("t", ["not", "map"], "err", 1)  # type: ignore[arg-type]


def test_default_enqueued_at_iso() -> None:
    """Omitting enqueued_at_iso still yields a non-empty ISO-like stamp."""

    queue = DeadLetterToolQueue()
    item = queue.enqueue("t", {"a": 1}, "boom", 4)
    assert "T" in item.enqueued_at_iso
