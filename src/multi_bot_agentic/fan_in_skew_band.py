"""Fan-in skew band guard.

Measures completion-time skew across fan-in branches and emits HITL bands.
Distinct from ``FanInBarrierGate`` (barrier join) and
``ToolCallWaveScheduler`` (wave scheduling). Fills a gap vs AutoGen /
CrewAI / LangGraph fan-in latency skew. Works with GPT-5.5 /
Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. Never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FanInSkewStatus:
    """Fan-in completion-time skew status."""

    session_id: str
    fastest_s: float
    slowest_s: float
    skew_ratio: float
    band: str
    requires_human_review: bool


class FanInSkewBandGuard:
    """Flag fan-in branches with high completion-time skew."""

    def check(
        self,
        session_id: str,
        *,
        fastest_s: float,
        slowest_s: float,
    ) -> FanInSkewStatus:
        """Return skew band from fastest vs slowest branch times.

        Args:
            session_id: Non-empty session id.
            fastest_s: Fastest branch completion seconds (``> 0``).
            slowest_s: Slowest branch completion seconds (``>= fastest_s``).

        Returns:
            FanInSkewStatus with ``requires_human_review=True``.
        """

        sid = session_id.strip()
        if not sid:
            raise ValueError("session_id must be non-empty")
        if fastest_s <= 0:
            raise ValueError("fastest_s must be > 0")
        if slowest_s < fastest_s:
            raise ValueError("slowest_s must be >= fastest_s")

        skew_ratio = round(slowest_s / fastest_s, 4)
        if skew_ratio <= 1.5:
            band = "balanced"
        elif skew_ratio <= 3.0:
            band = "skewed"
        else:
            band = "straggler"

        return FanInSkewStatus(
            session_id=sid,
            fastest_s=float(fastest_s),
            slowest_s=float(slowest_s),
            skew_ratio=float(skew_ratio),
            band=band,
            requires_human_review=True,
        )
