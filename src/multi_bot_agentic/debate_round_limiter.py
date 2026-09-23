"""Debate round limiter for multi-bot deliberation.

Caps debate rounds and emits HITL exhaust bands. Distinct from
``ConversationTurnBudgetGuard`` (session turns) and
``ConsensusConfidenceBandAdvisor`` (vote-share bands). Fills a gap vs
AutoGen / CrewAI / LangGraph unbounded debate loops. Works with GPT-5.5 /
Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. Never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DebateRoundStatus:
    """Debate round budget status.

    Attributes:
        session_id: Session identifier.
        rounds_used: Completed debate rounds.
        max_rounds: Hard cap.
        remaining: Rounds remaining.
        band: ``ok`` / ``near_limit`` / ``exhausted``.
        requires_human_review: Always True for HITL.
    """

    session_id: str
    rounds_used: int
    max_rounds: int
    remaining: int
    band: str
    requires_human_review: bool


class DebateRoundLimiter:
    """Limit multi-bot debate rounds with advisory bands."""

    def check(
        self,
        session_id: str,
        *,
        rounds_used: int,
        max_rounds: int = 5,
    ) -> DebateRoundStatus:
        """Return debate-round budget status.

        Args:
            session_id: Non-empty session id.
            rounds_used: Completed rounds (``>= 0``).
            max_rounds: Hard cap (``>= 1``).

        Returns:
            DebateRoundStatus with ``requires_human_review=True``.
        """

        sid = session_id.strip()
        if not sid:
            raise ValueError("session_id must be non-empty")
        if rounds_used < 0:
            raise ValueError("rounds_used must be >= 0")
        if max_rounds < 1:
            raise ValueError("max_rounds must be >= 1")

        remaining = max(0, max_rounds - rounds_used)
        if remaining == 0:
            band = "exhausted"
        elif remaining <= max(1, max_rounds // 5):
            band = "near_limit"
        else:
            band = "ok"

        return DebateRoundStatus(
            session_id=sid,
            rounds_used=int(rounds_used),
            max_rounds=int(max_rounds),
            remaining=int(remaining),
            band=band,
            requires_human_review=True,
        )
