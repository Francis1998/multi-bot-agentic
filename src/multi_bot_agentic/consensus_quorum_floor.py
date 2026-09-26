"""Consensus quorum floor guard.

Requires a minimum yes-vote count before consensus and emits HITL bands.
Distinct from ``VoteTieBreakPolicy`` (tie breaks) and
``ConsensusConfidenceBandAdvisor`` (winning-share bands). Fills a gap vs
AutoGen / CrewAI / LangGraph thin-quorum consensus. Works with GPT-5.5 /
Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. Never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ConsensusQuorumFloorStatus:
    """Consensus quorum floor status."""

    session_id: str
    yes_votes: int
    min_yes_votes: int
    shortfall: int
    band: str
    requires_human_review: bool


class ConsensusQuorumFloorGuard:
    """Gate consensus on a minimum yes-vote floor."""

    def check(
        self,
        session_id: str,
        *,
        yes_votes: int,
        min_yes_votes: int = 3,
    ) -> ConsensusQuorumFloorStatus:
        """Return quorum-floor status for a session.

        Args:
            session_id: Non-empty session id.
            yes_votes: Affirmative votes counted (``>= 0``).
            min_yes_votes: Required yes-vote floor (``>= 1``).

        Returns:
            ConsensusQuorumFloorStatus with ``requires_human_review=True``.
        """

        sid = session_id.strip()
        if not sid:
            raise ValueError("session_id must be non-empty")
        if yes_votes < 0:
            raise ValueError("yes_votes must be >= 0")
        if min_yes_votes < 1:
            raise ValueError("min_yes_votes must be >= 1")

        shortfall = max(0, min_yes_votes - yes_votes)
        if shortfall == 0:
            band = "quorum_met"
        elif yes_votes >= max(1, (min_yes_votes + 1) // 2):
            band = "near_quorum"
        else:
            band = "quorum_fail"

        return ConsensusQuorumFloorStatus(
            session_id=sid,
            yes_votes=int(yes_votes),
            min_yes_votes=int(min_yes_votes),
            shortfall=int(shortfall),
            band=band,
            requires_human_review=True,
        )
