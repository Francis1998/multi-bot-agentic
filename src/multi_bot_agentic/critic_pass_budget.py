"""Critic pass budget limiter for multi-bot revision loops.

Caps critic re-pass / revise loops and emits HITL exhaust bands. Distinct from
``CriticBotVerdictGate`` (accept/revise/reject) and ``DebateRoundLimiter``
(debate rounds). Fills a gap vs AutoGen / CrewAI / LangGraph unbounded critic
revision loops. Works with GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2.
Never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CriticPassBudgetStatus:
    """Critic pass budget status."""

    session_id: str
    passes_used: int
    max_passes: int
    remaining: int
    band: str
    requires_human_review: bool


class CriticPassBudgetLimiter:
    """Limit critic re-pass loops with advisory bands."""

    def check(
        self,
        session_id: str,
        *,
        passes_used: int,
        max_passes: int = 3,
    ) -> CriticPassBudgetStatus:
        """Return critic-pass budget status.

        Args:
            session_id: Non-empty session id.
            passes_used: Completed critic passes (``>= 0``).
            max_passes: Hard cap (``>= 1``).

        Returns:
            CriticPassBudgetStatus with ``requires_human_review=True``.
        """

        sid = session_id.strip()
        if not sid:
            raise ValueError("session_id must be non-empty")
        if passes_used < 0:
            raise ValueError("passes_used must be >= 0")
        if max_passes < 1:
            raise ValueError("max_passes must be >= 1")

        remaining = max(0, max_passes - passes_used)
        if remaining == 0:
            band = "exhausted"
        elif remaining <= max(1, max_passes // 3):
            band = "near_limit"
        else:
            band = "ok"

        return CriticPassBudgetStatus(
            session_id=sid,
            passes_used=int(passes_used),
            max_passes=int(max_passes),
            remaining=int(remaining),
            band=band,
            requires_human_review=True,
        )
