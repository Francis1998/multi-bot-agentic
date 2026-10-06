"""ToolRetryBudget band guard/advisor.

Flags retry_count pressure with HITL bands. Distinct from
``retry_backoff`` / ``TurnBudgetLimiter``.
Fills a gap vs AutoGen/CrewAI/LangGraph tool-retry budget guards.
Works with frontier multi-LLM stacks. Never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolRetryBudgetBandStatus:
    """ToolRetryBudgetBandGuard status."""

    session_id: str
    retry_count: float
    soft_limit: float
    hard_limit: float
    band: str
    requires_human_review: bool


class ToolRetryBudgetBandGuard:
    """Gate retry_count vs soft/hard limits."""

    def __init__(self, *, soft_limit: float = 3.0, hard_limit: float = 10.0) -> None:
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

    def check(self, session_id: str, *, retry_count: float) -> ToolRetryBudgetBandStatus:
        """Return band for observed retry_count.

        Args:
            session_id: Non-empty id.
            retry_count: Observed value (``>= 0``).

        Returns:
            ToolRetryBudgetBandStatus with ``requires_human_review=True``.
        """

        sid = session_id.strip()
        if not sid:
            raise ValueError("session_id must be non-empty")
        if retry_count < 0:
            raise ValueError("retry_count must be >= 0")

        if retry_count <= self._soft:
            band = "ok"
        elif retry_count <= self._hard:
            band = "elevated"
        else:
            band = "blocked"

        return ToolRetryBudgetBandStatus(
            session_id=sid,
            retry_count=float(retry_count),
            soft_limit=self._soft,
            hard_limit=self._hard,
            band=band,
            requires_human_review=True,
        )
