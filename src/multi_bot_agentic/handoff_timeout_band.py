"""HandoffTimeoutBandAdvisor band guard.

Flags timeout_ratio pressure with HITL bands. Distinct from
`AgentHandoffLatencyTracker` / `CriticTimeoutBandGuard`.
Fills a gap vs LangGraph/CrewAI/AutoGen handoff-timeout band monitors.
Works with frontier multi-LLM stacks. Never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HandoffTimeoutBandStatus:
    """HandoffTimeoutBandAdvisor status."""

    session_id: str
    timeout_ratio: float
    soft_limit: float
    hard_limit: float
    band: str
    requires_human_review: bool


class HandoffTimeoutBandAdvisor:
    """Gate timeout_ratio vs soft/hard limits."""

    def __init__(self, *, soft_limit: float = 0.25, hard_limit: float = 0.6) -> None:
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

    def advise(self, session_id: str, *, timeout_ratio: float) -> HandoffTimeoutBandStatus:
        """Return band for observed timeout_ratio.

        Args:
            session_id: Non-empty id.
            timeout_ratio: Observed value (>= 0).

        Returns:
            HandoffTimeoutBandStatus with ``requires_human_review=True``.
        """

        sid = session_id.strip()
        if not sid:
            raise ValueError("session_id must be non-empty")
        if timeout_ratio < 0:
            raise ValueError("timeout_ratio must be >= 0")

        if timeout_ratio <= self._soft:
            band = "ok"
        elif timeout_ratio <= self._hard:
            band = "elevated"
        else:
            band = "blocked"

        return HandoffTimeoutBandStatus(
            session_id=sid,
            timeout_ratio=float(timeout_ratio),
            soft_limit=self._soft,
            hard_limit=self._hard,
            band=band,
            requires_human_review=True,
        )
