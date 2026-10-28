"""MessageBusPartitionBandAdvisor band guard.

Flags partition_ratio pressure with HITL bands. Distinct from
`OrchestratorFanInStallBandAdvisor` / `SharedLockContentionBandAdvisor`.
Fills a gap vs LangGraph/CrewAI/AutoGen message-bus partition monitors.
Works with frontier multi-LLM stacks. Never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MessageBusPartitionStatus:
    """MessageBusPartitionBandAdvisor status."""

    session_id: str
    partition_ratio: float
    soft_limit: float
    hard_limit: float
    band: str
    requires_human_review: bool


class MessageBusPartitionBandAdvisor:
    """Gate partition_ratio vs soft/hard limits."""

    def __init__(self, *, soft_limit: float = 0.7, hard_limit: float = 0.95) -> None:
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

    def advise(self, session_id: str, *, partition_ratio: float) -> MessageBusPartitionStatus:
        """Return band for observed partition_ratio.

        Args:
            session_id: Non-empty id.
            partition_ratio: Observed value (>= 0).

        Returns:
            MessageBusPartitionStatus with ``requires_human_review=True``.
        """

        sid = session_id.strip()
        if not sid:
            raise ValueError("session_id must be non-empty")
        if partition_ratio < 0:
            raise ValueError("partition_ratio must be >= 0")

        if partition_ratio <= self._soft:
            band = "ok"
        elif partition_ratio <= self._hard:
            band = "elevated"
        else:
            band = "blocked"

        return MessageBusPartitionStatus(
            session_id=sid,
            partition_ratio=float(partition_ratio),
            soft_limit=self._soft,
            hard_limit=self._hard,
            band=band,
            requires_human_review=True,
        )
