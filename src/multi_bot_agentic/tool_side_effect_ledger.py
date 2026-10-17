"""ToolSideEffectLedgerAdvisor band guard.

Flags side_effect_ratio pressure with HITL bands. Distinct from
`ToolCallQuotaGuard` / `ToolIdempotencyCache`.
Fills a gap vs LangGraph/CrewAI/AutoGen tool side-effect ledger monitors.
Works with frontier multi-LLM stacks. Never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolSideEffectLedgerStatus:
    """ToolSideEffectLedgerAdvisor status."""

    session_id: str
    side_effect_ratio: float
    soft_limit: float
    hard_limit: float
    band: str
    requires_human_review: bool


class ToolSideEffectLedgerAdvisor:
    """Gate side_effect_ratio vs soft/hard limits."""

    def __init__(self, *, soft_limit: float = 0.3, hard_limit: float = 0.7) -> None:
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

    def advise(self, session_id: str, *, side_effect_ratio: float) -> ToolSideEffectLedgerStatus:
        """Return band for observed side_effect_ratio.

        Args:
            session_id: Non-empty id.
            side_effect_ratio: Observed value (>= 0).

        Returns:
            ToolSideEffectLedgerStatus with ``requires_human_review=True``.
        """

        sid = session_id.strip()
        if not sid:
            raise ValueError("session_id must be non-empty")
        if side_effect_ratio < 0:
            raise ValueError("side_effect_ratio must be >= 0")

        if side_effect_ratio <= self._soft:
            band = "ok"
        elif side_effect_ratio <= self._hard:
            band = "elevated"
        else:
            band = "blocked"

        return ToolSideEffectLedgerStatus(
            session_id=sid,
            side_effect_ratio=float(side_effect_ratio),
            soft_limit=self._soft,
            hard_limit=self._hard,
            band=band,
            requires_human_review=True,
        )
