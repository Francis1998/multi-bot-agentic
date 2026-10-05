"""CriticSelfConsistencyBand guard/advisor.

Flags disagreement_rate pressure with HITL bands. Distinct from
``CriticAgreementEntropyGate`` and ``CriticPairwiseKappaGate``.
Fills a gap vs AutoGen/CrewAI/LangGraph critic self-consistency bands.
Works with frontier multi-LLM stacks. Never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CriticSelfConsistencyBandStatus:
    """CriticSelfConsistencyBandGuard status."""

    session_id: str
    disagreement_rate: float
    soft_limit: float
    hard_limit: float
    band: str
    requires_human_review: bool


class CriticSelfConsistencyBandGuard:
    """Gate disagreement_rate vs soft/hard limits."""

    def __init__(self, *, soft_limit: float = 0.25, hard_limit: float = 0.5) -> None:
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

    def check(self, session_id: str, *, disagreement_rate: float) -> CriticSelfConsistencyBandStatus:
        """Return band for observed disagreement_rate.

        Args:
            session_id: Non-empty id.
            disagreement_rate: Observed value (``>= 0``).

        Returns:
            CriticSelfConsistencyBandStatus with ``requires_human_review=True``.
        """

        sid = session_id.strip()
        if not sid:
            raise ValueError("session_id must be non-empty")
        if disagreement_rate < 0:
            raise ValueError("disagreement_rate must be >= 0")

        if disagreement_rate <= self._soft:
            band = "ok"
        elif disagreement_rate <= self._hard:
            band = "elevated"
        else:
            band = "blocked"

        return CriticSelfConsistencyBandStatus(
            session_id=sid,
            disagreement_rate=float(disagreement_rate),
            soft_limit=self._soft,
            hard_limit=self._hard,
            band=band,
            requires_human_review=True,
        )
