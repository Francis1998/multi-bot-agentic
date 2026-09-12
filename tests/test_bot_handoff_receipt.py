"""Tests for BotHandoffReceiptStore."""

from __future__ import annotations

import pytest

from multi_bot_agentic.bot_handoff_receipt import BotHandoffReceiptStore


def test_issue_and_list_for() -> None:
    """issue stores a receipt; list_for returns matches for from or to bot."""

    store = BotHandoffReceiptStore()
    receipt = store.issue(
        from_bot="researcher",
        to_bot="writer",
        summary="draft outline ready",
        artifacts={"doc_id": "abc"},
        timestamp_iso="2026-09-12T12:00:00+00:00",
    )
    assert receipt.from_bot == "researcher"
    assert receipt.to_bot == "writer"
    assert receipt.summary == "draft outline ready"
    assert receipt.artifacts == {"doc_id": "abc"}
    assert receipt.timestamp_iso == "2026-09-12T12:00:00+00:00"
    assert receipt.receipt_id

    for_writer = store.list_for("writer")
    assert len(for_writer) == 1
    assert for_writer[0].receipt_id == receipt.receipt_id

    for_researcher = store.list_for("researcher")
    assert len(for_researcher) == 1


def test_list_for_filters_unrelated() -> None:
    """list_for ignores receipts that do not involve the bot."""

    store = BotHandoffReceiptStore()
    store.issue(from_bot="a", to_bot="b", summary="one")
    store.issue(from_bot="c", to_bot="d", summary="two")
    assert store.list_for("a")[0].summary == "one"
    assert store.list_for("d")[0].summary == "two"
    assert store.list_for("z") == []


def test_artifacts_copied() -> None:
    """Mutating the caller's artifacts dict does not change the receipt."""

    store = BotHandoffReceiptStore()
    arts = {"k": 1}
    receipt = store.issue(from_bot="a", to_bot="b", summary="s", artifacts=arts)
    arts["k"] = 99
    assert receipt.artifacts["k"] == 1


def test_default_timestamp_iso() -> None:
    """Omitting timestamp_iso still yields a non-empty ISO-like stamp."""

    store = BotHandoffReceiptStore()
    receipt = store.issue(from_bot="a", to_bot="b", summary="s")
    assert "T" in receipt.timestamp_iso
    assert len(receipt.timestamp_iso) >= 10


def test_rejects_empty_fields() -> None:
    """Empty from_bot / to_bot / summary / bot_id raise ValueError."""

    store = BotHandoffReceiptStore()
    with pytest.raises(ValueError, match="from_bot"):
        store.issue(from_bot="  ", to_bot="b", summary="s")
    with pytest.raises(ValueError, match="to_bot"):
        store.issue(from_bot="a", to_bot="", summary="s")
    with pytest.raises(ValueError, match="summary"):
        store.issue(from_bot="a", to_bot="b", summary=" ")
    with pytest.raises(ValueError, match="bot_id"):
        store.list_for("")


def test_rejects_non_mapping_artifacts() -> None:
    """Non-mapping artifacts raise TypeError."""

    store = BotHandoffReceiptStore()
    with pytest.raises(TypeError):
        store.issue(
            from_bot="a",
            to_bot="b",
            summary="s",
            artifacts=["not", "a", "map"],  # type: ignore[arg-type]
        )


def test_multiple_receipts_preserve_order() -> None:
    """list_for returns receipts in issue order."""

    store = BotHandoffReceiptStore()
    r1 = store.issue(from_bot="x", to_bot="y", summary="first")
    r2 = store.issue(from_bot="y", to_bot="z", summary="second")
    listed = store.list_for("y")
    assert [r.receipt_id for r in listed] == [r1.receipt_id, r2.receipt_id]
