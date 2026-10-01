"""Planner beam-width limiter.

Caps planner beam width with HITL bands. Distinct from
``DebateRoundLimiter`` and ``PlannerReplanBudgetLimiter``.
Fills a gap vs AutoGen / CrewAI / LangGraph planner beam-width
controls. Works with GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x /
Kimi K2. Never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlannerBeamWidthStatus:
    """Planner beam-width status."""

    session_id: str
    beam_width: int
    soft_limit: int
    hard_limit: int
    band: str
    requires_human_review: bool


class PlannerBeamWidthLimiter:
    """Gate planner beam width vs soft/hard limits."""

    def __init__(self, *, soft_limit: int = 4, hard_limit: int = 8) -> None:
        """Initialize soft/hard beam-width limits.

        Args:
            soft_limit: Soft max beam width (``> 0``).
            hard_limit: Hard max beam width (``> soft_limit``).
        """

        if soft_limit <= 0:
            raise ValueError("soft_limit must be > 0")
        if hard_limit <= soft_limit:
            raise ValueError("hard_limit must be > soft_limit")
        self._soft = soft_limit
        self._hard = hard_limit

    def check(self, session_id: str, *, beam_width: int) -> PlannerBeamWidthStatus:
        """Return beam-width band for one planner step.

        Args:
            session_id: Non-empty session id.
            beam_width: Requested beam width (``>= 1``).

        Returns:
            PlannerBeamWidthStatus with ``requires_human_review=True``.
        """

        sid = session_id.strip()
        if not sid:
            raise ValueError("session_id must be non-empty")
        if beam_width < 1:
            raise ValueError("beam_width must be >= 1")

        if beam_width <= self._soft:
            band = "ok"
        elif beam_width <= self._hard:
            band = "elevated"
        else:
            band = "blocked"

        return PlannerBeamWidthStatus(
            session_id=sid,
            beam_width=int(beam_width),
            soft_limit=self._soft,
            hard_limit=self._hard,
            band=band,
            requires_human_review=True,
        )
