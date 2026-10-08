"""AgentHandoffLatencyAdvisor band advisor.

Advises latency_ms vs soft/hard budgets with HITL bands.
Distinct from `AgentHandoffDepthLimiter` / `MultiBotLatencyBudgetAdvisor`.
Fills a gap vs AutoGen/CrewAI/LangGraph agent-handoff latency advisors.
Works with frontier multi-LLM stacks. Never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentHandoffLatencyAdvice:
    """AgentHandoffLatencyAdvisor advice."""

    session_id: str
    latency_ms: float
    soft_limit: float
    hard_limit: float
    band: str
    requires_human_review: bool


class AgentHandoffLatencyAdvisor:
    """Advise latency_ms bands."""

    def advise(
        self,
        session_id: str,
        *,
        latency_ms: float,
        soft_limit: float = 0.2,
        hard_limit: float = 0.6,
    ) -> AgentHandoffLatencyAdvice:
        """Return band for observed latency_ms."""

        sid = session_id.strip()
        if not sid:
            raise ValueError("session_id must be non-empty")
        if latency_ms < 0:
            raise ValueError("latency_ms must be >= 0")
        if soft_limit <= 0:
            raise ValueError("soft_limit must be > 0")
        if hard_limit <= soft_limit:
            raise ValueError("hard_limit must be > soft_limit")

        if latency_ms <= soft_limit:
            band = "ok"
        elif latency_ms <= hard_limit:
            band = "elevated"
        else:
            band = "blocked"

        return AgentHandoffLatencyAdvice(
            session_id=sid,
            latency_ms=float(latency_ms),
            soft_limit=float(soft_limit),
            hard_limit=float(hard_limit),
            band=band,
            requires_human_review=True,
        )
