"""Agent handoff depth limiter.

Caps chained bot-to-bot handoff depth per session and emits HITL bands.
Distinct from ``BotHandoffReceiptStore`` (receipt audit) and
``BotSpawnBudgetLimiter`` (spawn caps). Fills a gap vs AutoGen /
CrewAI / LangGraph unbounded nested handoffs. Works with GPT-5.5 /
Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. Never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentHandoffDepthStatus:
    """Agent handoff depth status."""

    session_id: str
    handoff_depth: int
    max_depth: int
    remaining: int
    band: str
    requires_human_review: bool


class AgentHandoffDepthLimiter:
    """Limit chained handoff depth per session."""

    def check(
        self,
        session_id: str,
        *,
        handoff_depth: int,
        max_depth: int = 4,
    ) -> AgentHandoffDepthStatus:
        """Return handoff-depth status for a session.

        Args:
            session_id: Non-empty session id.
            handoff_depth: Current nested handoff depth (``>= 0``).
            max_depth: Hard depth cap (``>= 1``).

        Returns:
            AgentHandoffDepthStatus with ``requires_human_review=True``.
        """

        sid = session_id.strip()
        if not sid:
            raise ValueError("session_id must be non-empty")
        if handoff_depth < 0:
            raise ValueError("handoff_depth must be >= 0")
        if max_depth < 1:
            raise ValueError("max_depth must be >= 1")

        remaining = max(0, max_depth - handoff_depth)
        if remaining == 0:
            band = "exhausted"
        elif remaining <= max(1, max_depth // 4):
            band = "near_limit"
        else:
            band = "ok"

        return AgentHandoffDepthStatus(
            session_id=sid,
            handoff_depth=int(handoff_depth),
            max_depth=int(max_depth),
            remaining=int(remaining),
            band=band,
            requires_human_review=True,
        )
