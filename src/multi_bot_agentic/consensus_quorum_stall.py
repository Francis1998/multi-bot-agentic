"""ConsensusQuorumStallAdvisor band guard.

Flags stall_ratio pressure with HITL bands. Distinct from
`ConsensusQuorumBandGuard` / `ConsensusTimeoutBandGuard`.
Fills a gap vs LangGraph/CrewAI/AutoGen consensus quorum-stall monitors.
Works with frontier multi-LLM stacks. Never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ConsensusQuorumStallStatus:
    """ConsensusQuorumStallAdvisor status."""

    session_id: str
    stall_ratio: float
    soft_limit: float
    hard_limit: float
    band: str
    requires_human_review: bool


class ConsensusQuorumStallAdvisor:
    """Gate stall_ratio vs soft/hard limits."""

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

    def advise(self, session_id: str, *, stall_ratio: float) -> ConsensusQuorumStallStatus:
        """Return band for observed stall_ratio.

        Args:
            session_id: Non-empty id.
            stall_ratio: Observed value (>= 0).

        Returns:
            ConsensusQuorumStallStatus with ``requires_human_review=True``.
        """

        sid = session_id.strip()
        if not sid:
            raise ValueError("session_id must be non-empty")
        if stall_ratio < 0:
            raise ValueError("stall_ratio must be >= 0")

        if stall_ratio <= self._soft:
            band = "ok"
        elif stall_ratio <= self._hard:
            band = "elevated"
        else:
            band = "blocked"

        return ConsensusQuorumStallStatus(
            session_id=sid,
            stall_ratio=float(stall_ratio),
            soft_limit=self._soft,
            hard_limit=self._hard,
            band=band,
            requires_human_review=True,
        )
