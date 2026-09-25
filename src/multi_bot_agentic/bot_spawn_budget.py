"""Bot spawn budget limiter.

Caps dynamic bot spawns per session and emits HITL bands.
Distinct from ``BotIdleTimeoutEvictor`` (idle eviction) and
``ConversationTurnBudgetGuard`` (turns). Fills a gap vs AutoGen /
CrewAI / LangGraph unbounded agent spawning. Works with GPT-5.5 /
Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. Never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BotSpawnBudgetStatus:
    """Bot spawn budget status."""

    session_id: str
    bots_spawned: int
    max_bots: int
    remaining: int
    band: str
    requires_human_review: bool


class BotSpawnBudgetLimiter:
    """Limit dynamic bot spawns per session."""

    def check(
        self,
        session_id: str,
        *,
        bots_spawned: int,
        max_bots: int = 8,
    ) -> BotSpawnBudgetStatus:
        """Return spawn-budget status for a session.

        Args:
            session_id: Non-empty session id.
            bots_spawned: Bots already spawned (``>= 0``).
            max_bots: Hard spawn cap (``>= 1``).

        Returns:
            BotSpawnBudgetStatus with ``requires_human_review=True``.
        """

        sid = session_id.strip()
        if not sid:
            raise ValueError("session_id must be non-empty")
        if bots_spawned < 0:
            raise ValueError("bots_spawned must be >= 0")
        if max_bots < 1:
            raise ValueError("max_bots must be >= 1")

        remaining = max(0, max_bots - bots_spawned)
        if remaining == 0:
            band = "exhausted"
        elif remaining <= max(1, max_bots // 4):
            band = "near_limit"
        else:
            band = "ok"

        return BotSpawnBudgetStatus(
            session_id=sid,
            bots_spawned=int(bots_spawned),
            max_bots=int(max_bots),
            remaining=int(remaining),
            band=band,
            requires_human_review=True,
        )
