"""Majority / plurality vote aggregator across bot answers.

Collects answers from multiple bots and returns a consensus winner for
HITL-style multi-bot agreement. Distinct from ``CriticBotVerdictGate``
(accept/revise/reject on one producer output) and ``ParallelFanOut``
(order-preserving task execution) — this is a thin, stdlib-only vote
tally for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 multi-bot
crews. Fills a gap vs AutoGen/CrewAI/LangGraph, which often lack a
first-class majority/plurality consensus aggregator separate from the
critic or fan-out runtime.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class BotVote:
    """One bot's answer in a consensus round.

    Attributes:
        bot_id: Voting bot identifier.
        answer: Normalized answer text.
    """

    bot_id: str
    answer: str


@dataclass(frozen=True)
class VoteConsensusResult:
    """Outcome of aggregating bot votes.

    Attributes:
        winner: Winning answer, or None on empty/tie (majority) / empty.
        tally: Answer → vote count mapping.
        mode: ``majority`` or ``plurality``.
        total_votes: Number of votes cast.
        is_tie: True when top answers share the same count.
        majority_reached: True when winner has strictly more than half.
    """

    winner: str | None
    tally: Mapping[str, int]
    mode: str
    total_votes: int
    is_tie: bool
    majority_reached: bool


class BotVoteConsensusAggregator:
    """Majority or plurality consensus over bot answers.

    Caller-driven v1: ``add_vote`` per bot, ``aggregate`` for the result,
    ``clear`` between rounds. Never performs network I/O.
    """

    _VALID_MODES = frozenset({"majority", "plurality"})

    def __init__(self, *, mode: str = "majority") -> None:
        """Create a vote aggregator.

        Args:
            mode: ``majority`` (need >50%) or ``plurality`` (most votes win;
                ties yield ``winner=None``).

        Raises:
            ValueError: When ``mode`` is invalid.
        """

        normalized = mode.strip().lower()
        if normalized not in self._VALID_MODES:
            raise ValueError("mode must be 'majority' or 'plurality'")
        self._mode = normalized
        self._votes: dict[str, str] = {}

    @property
    def mode(self) -> str:
        """Aggregation mode (``majority`` or ``plurality``)."""

        return self._mode

    def add_vote(self, *, bot_id: str, answer: str) -> BotVote:
        """Record or replace a bot's vote.

        Args:
            bot_id: Voting bot identifier (non-empty).
            answer: Answer text (non-empty after strip).

        Returns:
            Stored BotVote with normalized fields.

        Raises:
            ValueError: When ``bot_id`` or ``answer`` is empty.
        """

        bid = self._require_nonempty(bot_id, "bot_id")
        text = self._require_nonempty(answer, "answer")
        vote = BotVote(bot_id=bid, answer=text)
        self._votes[bid] = text
        return vote

    def aggregate(self) -> VoteConsensusResult:
        """Tally votes and return consensus according to ``mode``.

        Returns:
            VoteConsensusResult. Empty vote sets yield ``winner=None``.
            Majority mode returns ``winner=None`` when no answer exceeds
            half the votes (including ties). Plurality returns the top
            answer unless tied for first.
        """

        total = len(self._votes)
        if total == 0:
            return VoteConsensusResult(
                winner=None,
                tally={},
                mode=self._mode,
                total_votes=0,
                is_tie=False,
                majority_reached=False,
            )
        counts = Counter(self._votes.values())
        tally = dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))
        top_count = next(iter(tally.values()))
        leaders = [ans for ans, n in tally.items() if n == top_count]
        is_tie = len(leaders) > 1
        majority_reached = top_count * 2 > total
        if self._mode == "majority":
            winner = leaders[0] if majority_reached and not is_tie else None
        else:
            winner = None if is_tie else leaders[0]
        return VoteConsensusResult(
            winner=winner,
            tally=tally,
            mode=self._mode,
            total_votes=total,
            is_tie=is_tie,
            majority_reached=majority_reached,
        )

    def clear(self) -> None:
        """Drop all recorded votes."""

        self._votes.clear()

    def votes(self) -> list[BotVote]:
        """Return current votes sorted by bot_id."""

        return [BotVote(bot_id=bid, answer=ans) for bid, ans in sorted(self._votes.items())]

    @staticmethod
    def _require_nonempty(value: str, field: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError(f"{field} must be non-empty")
        return stripped
