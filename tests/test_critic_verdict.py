"""Tests for CriticBotVerdictGate."""

from __future__ import annotations

import pytest

from multi_bot_agentic.critic_verdict import CriticBotVerdictGate, CriticVerdict


def test_submit_creates_pending_review() -> None:
    """submit stores a pending review with the producer output."""

    gate = CriticBotVerdictGate()
    review = gate.submit(bot_id="writer", output_text="Draft answer")
    assert review.pending is True
    assert review.verdict is None
    assert review.bot_id == "writer"
    assert review.output_text == "Draft answer"
    assert gate.get(review.review_id).pending is True


def test_decide_accept() -> None:
    """accept closes the review and clears pending."""

    gate = CriticBotVerdictGate()
    review = gate.submit(bot_id="writer", output_text="ok")
    done = gate.decide(review.review_id, verdict=CriticVerdict.ACCEPT, critique="looks good")
    assert done.verdict is CriticVerdict.ACCEPT
    assert done.pending is False
    assert done.critique == "looks good"
    assert gate.list_pending() == []


def test_decide_revise_requires_hint() -> None:
    """revise without a revision_hint raises ValueError."""

    gate = CriticBotVerdictGate()
    review = gate.submit(bot_id="writer", output_text="draft")
    with pytest.raises(ValueError, match="revision_hint"):
        gate.decide(review.review_id, verdict=CriticVerdict.REVISE, critique="needs work")
    done = gate.decide(
        review.review_id,
        verdict=CriticVerdict.REVISE,
        critique="too vague",
        revision_hint="add citations",
    )
    assert done.verdict is CriticVerdict.REVISE
    assert done.revision_hint == "add citations"


def test_decide_reject() -> None:
    """reject records critique and is no longer pending."""

    gate = CriticBotVerdictGate()
    review = gate.submit(bot_id="writer", output_text="bad")
    done = gate.decide(review.review_id, verdict=CriticVerdict.REJECT, critique="unsafe")
    assert done.verdict is CriticVerdict.REJECT
    assert done.critique == "unsafe"


def test_list_pending_filters_decided() -> None:
    """list_pending returns only undecided reviews in insertion order."""

    gate = CriticBotVerdictGate()
    a = gate.submit(bot_id="a", output_text="one")
    b = gate.submit(bot_id="b", output_text="two")
    gate.decide(a.review_id, verdict=CriticVerdict.ACCEPT)
    pending = gate.list_pending()
    assert [p.review_id for p in pending] == [b.review_id]


def test_double_decide_raises() -> None:
    """Deciding an already-decided review raises ValueError."""

    gate = CriticBotVerdictGate()
    review = gate.submit(bot_id="w", output_text="x")
    gate.decide(review.review_id, verdict=CriticVerdict.ACCEPT)
    with pytest.raises(ValueError, match="already decided"):
        gate.decide(review.review_id, verdict=CriticVerdict.REJECT)


def test_unknown_review_raises_key_error() -> None:
    """get/decide on unknown ids raise KeyError."""

    gate = CriticBotVerdictGate()
    with pytest.raises(KeyError, match="unknown review_id"):
        gate.get("missing")
    with pytest.raises(KeyError, match="unknown review_id"):
        gate.decide("missing", verdict=CriticVerdict.ACCEPT)


def test_rejects_empty_fields() -> None:
    """Empty bot_id, output_text, or review_id raises ValueError."""

    gate = CriticBotVerdictGate()
    with pytest.raises(ValueError, match="bot_id"):
        gate.submit(bot_id="  ", output_text="x")
    with pytest.raises(ValueError, match="output_text"):
        gate.submit(bot_id="bot", output_text="")
    with pytest.raises(ValueError, match="review_id"):
        gate.get(" ")
