"""AgentMemoryPoisonBandAdvisor band guard.

Flags poison_ratio pressure with HITL bands. Distinct from
`SharedMemoryConflictBandAdvisor` / `PromptLeakBandAdvisor`.
Fills a gap vs LangGraph/CrewAI/AutoGen agent-memory poison monitors.
Works with frontier multi-LLM stacks. Never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentMemoryPoisonBandStatus:
    """AgentMemoryPoisonBandAdvisor status."""

    session_id: str
    poison_ratio: float
    soft_limit: float
    hard_limit: float
    band: str
    requires_human_review: bool


class AgentMemoryPoisonBandAdvisor:
    """Gate poison_ratio vs soft/hard limits."""

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

    def advise(self, session_id: str, *, poison_ratio: float) -> AgentMemoryPoisonBandStatus:
        """Return band for observed poison_ratio.

        Args:
            session_id: Non-empty id.
            poison_ratio: Observed value (>= 0).

        Returns:
            AgentMemoryPoisonBandStatus with ``requires_human_review=True``.
        """

        sid = session_id.strip()
        if not sid:
            raise ValueError("session_id must be non-empty")
        if poison_ratio < 0:
            raise ValueError("poison_ratio must be >= 0")

        if poison_ratio <= self._soft:
            band = "ok"
        elif poison_ratio <= self._hard:
            band = "elevated"
        else:
            band = "blocked"

        return AgentMemoryPoisonBandStatus(
            session_id=sid,
            poison_ratio=float(poison_ratio),
            soft_limit=self._soft,
            hard_limit=self._hard,
            band=band,
            requires_human_review=True,
        )
