"""ConsensusQuorum band guard/advisor.

Flags shortfall_ratio pressure with HITL bands. Distinct from
``VoteTieBreakAdvisor`` / ``CriticSelfConsistencyBandGuard``.
Fills a gap vs AutoGen/CrewAI/LangGraph consensus quorum band guards.
Works with frontier multi-LLM stacks. Never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ConsensusQuorumBandStatus:
    """ConsensusQuorumBandGuard status."""

    session_id: str
    shortfall_ratio: float
    soft_limit: float
    hard_limit: float
    band: str
    requires_human_review: bool


class ConsensusQuorumBandGuard:
    """Gate shortfall_ratio vs soft/hard limits."""

    def __init__(self, *, soft_limit: float = 0.2, hard_limit: float = 0.5) -> None:
        """Initialize limits.

        Args:
            soft_limit: Soft max (``> 0``).
            hard_limit: Hard max (``> soft_limit``).
        """

        if soft_limit <= 0:
            raise ValueError("soft_limit must be > 0")
        if hard_limit <= soft_limit:
            raise ValueError("hard_limit must be > soft_limit")
        self._soft = soft_limit
        self._hard = hard_limit

    def check(self, session_id: str, *, shortfall_ratio: float) -> ConsensusQuorumBandStatus:
        """Return band for observed shortfall_ratio.

        Args:
            session_id: Non-empty id.
            shortfall_ratio: Observed quorum shortfall (``>= 0``).

        Returns:
            ConsensusQuorumBandStatus with ``requires_human_review=True``.
        """

        sid = session_id.strip()
        if not sid:
            raise ValueError("session_id must be non-empty")
        if shortfall_ratio < 0:
            raise ValueError("shortfall_ratio must be >= 0")

        if shortfall_ratio <= self._soft:
            band = "ok"
        elif shortfall_ratio <= self._hard:
            band = "elevated"
        else:
            band = "blocked"

        return ConsensusQuorumBandStatus(
            session_id=sid,
            shortfall_ratio=float(shortfall_ratio),
            soft_limit=self._soft,
            hard_limit=self._hard,
            band=band,
            requires_human_review=True,
        )
