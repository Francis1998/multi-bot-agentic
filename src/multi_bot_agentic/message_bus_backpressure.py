"""MessageBusBackpressure guard/advisor.

Flags queue_depth pressure with HITL bands. Distinct from
``TurnBudgetLimiter`` and ``BotIdleTimeout``.
Fills a gap vs AutoGen/CrewAI/LangGraph message-bus backpressure advisors.
Works with frontier multi-LLM stacks. Never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MessageBusBackpressureStatus:
    """MessageBusBackpressureAdvisor status."""

    session_id: str
    queue_depth: float
    soft_limit: float
    hard_limit: float
    band: str
    requires_human_review: bool


class MessageBusBackpressureAdvisor:
    """Gate queue_depth vs soft/hard limits."""

    def __init__(self, *, soft_limit: float = 100.0, hard_limit: float = 500.0) -> None:
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

    def advise(self, session_id: str, *, queue_depth: float) -> MessageBusBackpressureStatus:
        """Return band for observed queue_depth.

        Args:
            session_id: Non-empty id.
            queue_depth: Observed value (``>= 0``).

        Returns:
            MessageBusBackpressureStatus with ``requires_human_review=True``.
        """

        sid = session_id.strip()
        if not sid:
            raise ValueError("session_id must be non-empty")
        if queue_depth < 0:
            raise ValueError("queue_depth must be >= 0")

        if queue_depth <= self._soft:
            band = "ok"
        elif queue_depth <= self._hard:
            band = "elevated"
        else:
            band = "blocked"

        return MessageBusBackpressureStatus(
            session_id=sid,
            queue_depth=float(queue_depth),
            soft_limit=self._soft,
            hard_limit=self._hard,
            band=band,
            requires_human_review=True,
        )
