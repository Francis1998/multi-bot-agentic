"""MemoryNamespaceLeakAdvisor band guard.

Flags leak_ratio pressure with HITL bands. Distinct from
`BlackboardLeaseThrashAdvisor` / `WorkerStarvationBandAdvisor`.
Fills a gap vs LangGraph/CrewAI/AutoGen memory-namespace leak monitors.
Works with frontier multi-LLM stacks. Never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MemoryNamespaceLeakStatus:
    """MemoryNamespaceLeakAdvisor status."""

    session_id: str
    leak_ratio: float
    soft_limit: float
    hard_limit: float
    band: str
    requires_human_review: bool


class MemoryNamespaceLeakAdvisor:
    """Gate leak_ratio vs soft/hard limits."""

    def __init__(self, *, soft_limit: float = 0.2, hard_limit: float = 0.55) -> None:
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

    def advise(self, session_id: str, *, leak_ratio: float) -> MemoryNamespaceLeakStatus:
        """Return band for observed leak_ratio.

        Args:
            session_id: Non-empty id.
            leak_ratio: Observed value (>= 0).

        Returns:
            MemoryNamespaceLeakStatus with ``requires_human_review=True``.
        """

        sid = session_id.strip()
        if not sid:
            raise ValueError("session_id must be non-empty")
        if leak_ratio < 0:
            raise ValueError("leak_ratio must be >= 0")

        if leak_ratio <= self._soft:
            band = "ok"
        elif leak_ratio <= self._hard:
            band = "elevated"
        else:
            band = "blocked"

        return MemoryNamespaceLeakStatus(
            session_id=sid,
            leak_ratio=float(leak_ratio),
            soft_limit=self._soft,
            hard_limit=self._hard,
            band=band,
            requires_human_review=True,
        )
