"""CriticTokenBudgetBand guard/advisor.

Flags tokens_used pressure with HITL bands. Distinct from
``SessionTokenBudgetLedger`` and ``CriticLatencySloBandGuard``.
Fills a gap vs AutoGen/CrewAI/LangGraph critic token-budget bands.
Works with frontier multi-LLM stacks. Never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CriticTokenBudgetBandStatus:
    """CriticTokenBudgetBandGuard status."""

    session_id: str
    tokens_used: float
    soft_limit: float
    hard_limit: float
    band: str
    requires_human_review: bool


class CriticTokenBudgetBandGuard:
    """Gate tokens_used vs soft/hard limits."""

    def __init__(self, *, soft_limit: float = 4000.0, hard_limit: float = 8000.0) -> None:
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

    def check(self, session_id: str, *, tokens_used: float) -> CriticTokenBudgetBandStatus:
        """Return band for observed tokens_used.

        Args:
            session_id: Non-empty id.
            tokens_used: Observed value (``>= 0``).

        Returns:
            CriticTokenBudgetBandStatus with ``requires_human_review=True``.
        """

        sid = session_id.strip()
        if not sid:
            raise ValueError("session_id must be non-empty")
        if tokens_used < 0:
            raise ValueError("tokens_used must be >= 0")

        if tokens_used <= self._soft:
            band = "ok"
        elif tokens_used <= self._hard:
            band = "elevated"
        else:
            band = "blocked"

        return CriticTokenBudgetBandStatus(
            session_id=sid,
            tokens_used=float(tokens_used),
            soft_limit=self._soft,
            hard_limit=self._hard,
            band=band,
            requires_human_review=True,
        )
