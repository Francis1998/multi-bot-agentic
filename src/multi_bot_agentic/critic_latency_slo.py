"""CriticLatencySloBand guard.

Flags latency ms pressure with HITL bands. Distinct from
``CriticTimeoutBandGuard and CriticPassBudgetLimiter``.
Fills a gap vs AutoGen/CrewAI/LangGraph critic latency SLO controls.
Works with GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x /
Kimi K2. Never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CriticLatencySloStatus:
    """CriticLatencySloBandGuard status."""

    critic_id: str
    latency_ms: float
    soft_limit: float
    hard_limit: float
    band: str
    requires_human_review: bool


class CriticLatencySloBandGuard:
    """Gate latency ms vs soft/hard limits."""

    def __init__(self, *, soft_limit: float = 1500.0, hard_limit: float = 3000.0) -> None:
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

    def check(self, critic_id: str, *, latency_ms: float) -> CriticLatencySloStatus:
        """Return band for observed latency_ms.

        Args:
            critic_id: Non-empty id.
            latency_ms: Observed value (``>= 0``).

        Returns:
            CriticLatencySloStatus with ``requires_human_review=True``.
        """

        sid = critic_id.strip()
        if not sid:
            raise ValueError("critic_id must be non-empty")
        if latency_ms < 0:
            raise ValueError("latency_ms must be >= 0")

        if latency_ms <= self._soft:
            band = "ok"
        elif latency_ms <= self._hard:
            band = "elevated"
        else:
            band = "blocked"

        return CriticLatencySloStatus(
            critic_id=sid,
            latency_ms=float(latency_ms),
            soft_limit=self._soft,
            hard_limit=self._hard,
            band=band,
            requires_human_review=True,
        )
