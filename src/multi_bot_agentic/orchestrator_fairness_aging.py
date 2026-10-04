"""OrchestratorFairnessAging advisor.

Flags wait_age_seconds pressure with HITL bands. Distinct from
``MultiBotLatencyBudgetAllocator`` and ``FanInSkewBandGuard``.
Fills a gap vs AutoGen/CrewAI/LangGraph orchestrator fairness-aging controls.
Works with frontier multi-LLM stacks. Never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OrchestratorFairnessAgingStatus:
    """OrchestratorFairnessAgingAdvisor status."""

    session_id: str
    wait_age_seconds: float
    soft_limit: float
    hard_limit: float
    band: str
    requires_human_review: bool


class OrchestratorFairnessAgingAdvisor:
    """Advise wait_age_seconds vs soft/hard limits."""

    def __init__(self, *, soft_limit: float = 30.0, hard_limit: float = 120.0) -> None:
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

    def check(self, session_id: str, *, wait_age_seconds: float) -> OrchestratorFairnessAgingStatus:
        """Return band for observed wait_age_seconds.

        Args:
            session_id: Non-empty id.
            wait_age_seconds: Observed value (``>= 0``).

        Returns:
            OrchestratorFairnessAgingStatus with ``requires_human_review=True``.
        """

        sid = session_id.strip()
        if not sid:
            raise ValueError("session_id must be non-empty")
        if wait_age_seconds < 0:
            raise ValueError("wait_age_seconds must be >= 0")

        if wait_age_seconds <= self._soft:
            band = "ok"
        elif wait_age_seconds <= self._hard:
            band = "elevated"
        else:
            band = "blocked"

        return OrchestratorFairnessAgingStatus(
            session_id=sid,
            wait_age_seconds=float(wait_age_seconds),
            soft_limit=self._soft,
            hard_limit=self._hard,
            band=band,
            requires_human_review=True,
        )
