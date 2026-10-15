"""OrchestratorFanoutBudgetBandAdvisor band guard.

Flags fanout_ratio pressure with HITL bands. Distinct from
`OrchestratorCascadeFailureAdvisor` / `OrchestratorFairnessAgingAdvisor`.
Fills a gap vs AutoGen/CrewAI/LangGraph orchestrator fan-out budget monitors.
Works with frontier multi-LLM stacks. Never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OrchestratorFanoutBudgetBandStatus:
    """OrchestratorFanoutBudgetBandAdvisor status."""

    session_id: str
    fanout_ratio: float
    soft_limit: float
    hard_limit: float
    band: str
    requires_human_review: bool


class OrchestratorFanoutBudgetBandAdvisor:
    """Gate fanout_ratio vs soft/hard limits."""

    def __init__(self, *, soft_limit: float = 0.6, hard_limit: float = 0.9) -> None:
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

    def advise(self, session_id: str, *, fanout_ratio: float) -> OrchestratorFanoutBudgetBandStatus:
        """Return band for observed fanout_ratio.

        Args:
            session_id: Non-empty id.
            fanout_ratio: Observed value (>= 0).

        Returns:
            OrchestratorFanoutBudgetBandStatus with ``requires_human_review=True``.
        """

        sid = session_id.strip()
        if not sid:
            raise ValueError("session_id must be non-empty")
        if fanout_ratio < 0:
            raise ValueError("fanout_ratio must be >= 0")

        if fanout_ratio <= self._soft:
            band = "ok"
        elif fanout_ratio <= self._hard:
            band = "elevated"
        else:
            band = "blocked"

        return OrchestratorFanoutBudgetBandStatus(
            session_id=sid,
            fanout_ratio=float(fanout_ratio),
            soft_limit=self._soft,
            hard_limit=self._hard,
            band=band,
            requires_human_review=True,
        )
