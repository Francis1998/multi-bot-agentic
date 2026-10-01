"""Multi-bot latency budget allocator.

Allocates per-bot latency shares vs a session budget with HITL
bands. Distinct from ``TurnBudgetGuard`` and
``CriticTimeoutBandGuard``. Fills a gap vs AutoGen / CrewAI /
LangGraph multi-bot latency budget allocators. Works with
GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2.
Never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MultiBotLatencyBudgetStatus:
    """Multi-bot latency budget status."""

    session_id: str
    bot_id: str
    allocated_ms: float
    used_ms: float
    session_budget_ms: float
    utilization: float
    band: str
    requires_human_review: bool


class MultiBotLatencyBudgetAllocator:
    """Allocate and band per-bot latency vs a session budget."""

    def __init__(self, *, session_budget_ms: float = 30_000.0) -> None:
        """Initialize session latency budget.

        Args:
            session_budget_ms: Total session latency budget (``> 0``).
        """

        if session_budget_ms <= 0:
            raise ValueError("session_budget_ms must be > 0")
        self._budget = float(session_budget_ms)

    def check(
        self,
        session_id: str,
        *,
        bot_id: str,
        allocated_ms: float,
        used_ms: float,
    ) -> MultiBotLatencyBudgetStatus:
        """Return latency-budget band for one bot.

        Args:
            session_id: Non-empty session id.
            bot_id: Non-empty bot id.
            allocated_ms: Allocated share for the bot (``> 0``).
            used_ms: Used latency so far (``>= 0``).

        Returns:
            MultiBotLatencyBudgetStatus with ``requires_human_review=True``.
        """

        sid = session_id.strip()
        bid = bot_id.strip()
        if not sid:
            raise ValueError("session_id must be non-empty")
        if not bid:
            raise ValueError("bot_id must be non-empty")
        if allocated_ms <= 0:
            raise ValueError("allocated_ms must be > 0")
        if used_ms < 0:
            raise ValueError("used_ms must be >= 0")
        if allocated_ms > self._budget:
            raise ValueError("allocated_ms must be <= session_budget_ms")

        utilization = round(used_ms / allocated_ms, 4)
        if utilization <= 0.8:
            band = "within"
        elif utilization <= 1.0:
            band = "soft"
        else:
            band = "breach"

        return MultiBotLatencyBudgetStatus(
            session_id=sid,
            bot_id=bid,
            allocated_ms=float(allocated_ms),
            used_ms=float(used_ms),
            session_budget_ms=self._budget,
            utilization=float(utilization),
            band=band,
            requires_human_review=True,
        )
