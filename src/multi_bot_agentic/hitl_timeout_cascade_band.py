"""HitlTimeoutCascadeBandAdvisor band guard.

Flags cascade_ratio pressure with HITL bands. Distinct from
`HandoffTimeoutBandAdvisor` / `ToolTimeoutCascadeBandAdvisor`.
Fills a gap vs LangGraph/CrewAI/AutoGen HITL timeout-cascade monitors.
Works with frontier multi-LLM stacks. Never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HitlTimeoutCascadeBandStatus:
    """HitlTimeoutCascadeBandAdvisor status."""

    session_id: str
    cascade_ratio: float
    soft_limit: float
    hard_limit: float
    band: str
    requires_human_review: bool


class HitlTimeoutCascadeBandAdvisor:
    """Gate cascade_ratio vs soft/hard limits."""

    def __init__(self, *, soft_limit: float = 0.2, hard_limit: float = 0.5) -> None:
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

    def advise(self, session_id: str, *, cascade_ratio: float) -> HitlTimeoutCascadeBandStatus:
        """Return band for observed cascade_ratio.

        Args:
            session_id: Non-empty id.
            cascade_ratio: Observed value (>= 0).

        Returns:
            HitlTimeoutCascadeBandStatus with ``requires_human_review=True``.
        """

        sid = session_id.strip()
        if not sid:
            raise ValueError("session_id must be non-empty")
        if cascade_ratio < 0:
            raise ValueError("cascade_ratio must be >= 0")

        if cascade_ratio <= self._soft:
            band = "ok"
        elif cascade_ratio <= self._hard:
            band = "elevated"
        else:
            band = "blocked"

        return HitlTimeoutCascadeBandStatus(
            session_id=sid,
            cascade_ratio=float(cascade_ratio),
            soft_limit=self._soft,
            hard_limit=self._hard,
            band=band,
            requires_human_review=True,
        )
