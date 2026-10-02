"""Critic pairwise Cohen-kappa gate.

Gates critic pairwise Cohen-kappa agreement with HITL bands. Distinct from
``CriticAgreementEntropyGate`` and ``CriticVerdictDiversityGate``.
Fills a gap vs AutoGen/CrewAI/LangGraph critic pairwise Cohen-kappa agreement controls.
Works with GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x /
Kimi K2. Never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CriticPairwiseKappaStatus:
    """Critic pairwise kappa status."""

    session_id: str
    kappa: float
    soft_floor: float
    hard_floor: float
    band: str
    requires_human_review: bool


class CriticPairwiseKappaGate:
    """Gate critic pairwise Cohen-kappa vs soft/hard floors."""

    def __init__(self, *, soft_floor: float = 0.6, hard_floor: float = 0.2) -> None:
        """Initialize kappa floors.

        Args:
            soft_floor: Soft minimum kappa (``0 < soft_floor <= 1``).
            hard_floor: Hard minimum kappa (``0 <= hard_floor < soft_floor``).
        """

        if not 0.0 < soft_floor <= 1.0:
            raise ValueError("soft_floor must be in (0, 1]")
        if not 0.0 <= hard_floor < soft_floor:
            raise ValueError("hard_floor must be in [0, soft_floor)")
        self._soft = soft_floor
        self._hard = hard_floor

    def check(self, session_id: str, *, kappa: float) -> CriticPairwiseKappaStatus:
        """Return kappa band for one critic pair.

        Args:
            session_id: Non-empty session id.
            kappa: Observed Cohen kappa (``-1..1``).

        Returns:
            CriticPairwiseKappaStatus with ``requires_human_review=True``.
        """

        sid = session_id.strip()
        if not sid:
            raise ValueError("session_id must be non-empty")
        if kappa < -1.0 or kappa > 1.0:
            raise ValueError("kappa must be in [-1, 1]")

        if kappa >= self._soft:
            band = "ok"
        elif kappa >= self._hard:
            band = "elevated"
        else:
            band = "blocked"

        return CriticPairwiseKappaStatus(
            session_id=sid,
            kappa=float(kappa),
            soft_floor=self._soft,
            hard_floor=self._hard,
            band=band,
            requires_human_review=True,
        )
