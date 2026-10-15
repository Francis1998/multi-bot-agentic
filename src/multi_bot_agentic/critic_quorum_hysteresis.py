"""CriticQuorumHysteresisAdvisor band guard.

Flags hysteresis_score pressure with HITL bands. Distinct from
`ConsensusQuorumBandGuard` / `CriticSelfConsistencyBandGuard`.
Fills a gap vs AutoGen/CrewAI/LangGraph critic-quorum hysteresis monitors.
Works with frontier multi-LLM stacks. Never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CriticQuorumHysteresisStatus:
    """CriticQuorumHysteresisAdvisor status."""

    session_id: str
    hysteresis_score: float
    soft_limit: float
    hard_limit: float
    band: str
    requires_human_review: bool


class CriticQuorumHysteresisAdvisor:
    """Gate hysteresis_score vs soft/hard limits."""

    def __init__(self, *, soft_limit: float = 0.6, hard_limit: float = 0.9) -> None:
        """Initialize limits.

        Args:
            soft_limit: Soft max (> 0).
            hard_limit: Hard max (> soft_limit).
        """

        if soft_limit <= 0:
            raise ValueError("soft_limit must be > 0")
        if hard_limit <= soft_limit:
            raise ValueError("hard_limit must be > soft_limit")
        self._soft = soft_limit
        self._hard = hard_limit

    def advise(self, session_id: str, *, hysteresis_score: float) -> CriticQuorumHysteresisStatus:
        """Return band for observed hysteresis_score.

        Args:
            session_id: Non-empty id.
            hysteresis_score: Observed value (>= 0).

        Returns:
            CriticQuorumHysteresisStatus with ``requires_human_review=True``.
        """

        sid = session_id.strip()
        if not sid:
            raise ValueError("session_id must be non-empty")
        if hysteresis_score < 0:
            raise ValueError("hysteresis_score must be >= 0")

        if hysteresis_score <= self._soft:
            band = "ok"
        elif hysteresis_score <= self._hard:
            band = "elevated"
        else:
            band = "blocked"

        return CriticQuorumHysteresisStatus(
            session_id=sid,
            hysteresis_score=float(hysteresis_score),
            soft_limit=self._soft,
            hard_limit=self._hard,
            band=band,
            requires_human_review=True,
        )
