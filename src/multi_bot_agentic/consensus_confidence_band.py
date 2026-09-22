"""Consensus confidence band advisor for multi-bot vote shares.

Maps winning vote share into confidence bands for HITL review. Distinct from
``BotVoteConsensusAggregator`` (winner selection) and ``CriticBotVerdictGate``
(accept/revise/reject). Fills a gap vs AutoGen / CrewAI / LangGraph confidence
reporting. Works with GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2.
Never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ConsensusConfidenceBand:
    """Confidence band for a consensus outcome.

    Attributes:
        session_id: Session identifier.
        vote_share: Winning option share in ``[0, 1]``.
        band: ``low`` / ``medium`` / ``high`` / ``unanimous``.
        requires_human_review: Always True for HITL.
    """

    session_id: str
    vote_share: float
    band: str
    requires_human_review: bool


class ConsensusConfidenceBandAdvisor:
    """Advise confidence bands from winning vote share."""

    def advise(self, session_id: str, *, vote_share: float) -> ConsensusConfidenceBand:
        """Return a confidence band for ``vote_share``.

        Args:
            session_id: Non-empty session id.
            vote_share: Winning share in ``[0, 1]``.

        Returns:
            ConsensusConfidenceBand with ``requires_human_review=True``.
        """

        sid = session_id.strip()
        if not sid:
            raise ValueError("session_id must be non-empty")
        if not 0.0 <= vote_share <= 1.0:
            raise ValueError("vote_share must be in [0, 1]")

        if vote_share >= 1.0:
            band = "unanimous"
        elif vote_share >= 0.75:
            band = "high"
        elif vote_share >= 0.5:
            band = "medium"
        else:
            band = "low"

        return ConsensusConfidenceBand(
            session_id=sid,
            vote_share=float(vote_share),
            band=band,
            requires_human_review=True,
        )
