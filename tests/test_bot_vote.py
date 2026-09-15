"""Tests for BotVoteConsensusAggregator."""

from __future__ import annotations

import pytest

from multi_bot_agentic.bot_vote import BotVoteConsensusAggregator


def test_majority_winner_when_over_half() -> None:
    """majority mode picks the answer with strictly more than half."""

    agg = BotVoteConsensusAggregator(mode="majority")
    agg.add_vote(bot_id="a", answer="yes")
    agg.add_vote(bot_id="b", answer="yes")
    agg.add_vote(bot_id="c", answer="no")
    result = agg.aggregate()
    assert result.winner == "yes"
    assert result.majority_reached is True
    assert result.is_tie is False
    assert result.tally == {"yes": 2, "no": 1}


def test_majority_no_winner_without_over_half() -> None:
    """majority mode returns None when no answer exceeds half."""

    agg = BotVoteConsensusAggregator(mode="majority")
    agg.add_vote(bot_id="a", answer="x")
    agg.add_vote(bot_id="b", answer="y")
    result = agg.aggregate()
    assert result.winner is None
    assert result.majority_reached is False
    assert result.is_tie is True


def test_plurality_picks_most_votes() -> None:
    """plurality mode picks the plurality winner without needing >50%."""

    agg = BotVoteConsensusAggregator(mode="plurality")
    agg.add_vote(bot_id="a", answer="red")
    agg.add_vote(bot_id="b", answer="blue")
    agg.add_vote(bot_id="c", answer="red")
    agg.add_vote(bot_id="d", answer="green")
    result = agg.aggregate()
    assert result.winner == "red"
    assert result.majority_reached is False
    assert result.total_votes == 4


def test_plurality_tie_yields_no_winner() -> None:
    """plurality ties set is_tie and leave winner None."""

    agg = BotVoteConsensusAggregator(mode="plurality")
    agg.add_vote(bot_id="a", answer="x")
    agg.add_vote(bot_id="b", answer="y")
    result = agg.aggregate()
    assert result.winner is None
    assert result.is_tie is True


def test_add_vote_replaces_same_bot() -> None:
    """A bot may change its answer; only the latest counts."""

    agg = BotVoteConsensusAggregator(mode="majority")
    agg.add_vote(bot_id="a", answer="old")
    agg.add_vote(bot_id="a", answer="new")
    agg.add_vote(bot_id="b", answer="new")
    result = agg.aggregate()
    assert result.total_votes == 2
    assert result.winner == "new"
    assert [v.answer for v in agg.votes()] == ["new", "new"]


def test_clear_resets_votes() -> None:
    """clear drops all votes for a fresh round."""

    agg = BotVoteConsensusAggregator()
    agg.add_vote(bot_id="a", answer="yes")
    agg.clear()
    empty = agg.aggregate()
    assert empty.total_votes == 0
    assert empty.winner is None
    assert empty.tally == {}


def test_constructor_rejects_bad_mode() -> None:
    """Invalid mode raises ValueError."""

    with pytest.raises(ValueError, match="mode"):
        BotVoteConsensusAggregator(mode="unanimous")


def test_rejects_empty_bot_or_answer() -> None:
    """Empty bot_id or answer raises ValueError."""

    agg = BotVoteConsensusAggregator()
    with pytest.raises(ValueError, match="bot_id"):
        agg.add_vote(bot_id="  ", answer="yes")
    with pytest.raises(ValueError, match="answer"):
        agg.add_vote(bot_id="a", answer=" ")
