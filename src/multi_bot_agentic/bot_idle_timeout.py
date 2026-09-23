"""Bot idle timeout evictor for multi-bot runtimes.

Marks bots for HITL eviction after idle seconds exceed a threshold. Distinct
from ``BotHeartbeatLivenessWatchdog`` (heartbeat misses) and
``SessionTtlExpirer`` (session TTL). Fills a gap vs AutoGen / CrewAI /
LangGraph idle worker cleanup. Works with GPT-5.5 / Claude Sonnet 4.6 /
Gemini 3.x / Kimi K2. Never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BotIdleTimeoutReport:
    """Idle timeout advisory for one bot.

    Attributes:
        bot_id: Bot identifier.
        idle_seconds: Seconds since last activity.
        timeout_seconds: Eviction threshold.
        band: ``active`` / ``idle`` / ``evict``.
        requires_human_review: Always True for HITL.
    """

    bot_id: str
    idle_seconds: float
    timeout_seconds: float
    band: str
    requires_human_review: bool


class BotIdleTimeoutEvictor:
    """Advise idle/evict bands from bot idle seconds."""

    def check(
        self,
        bot_id: str,
        *,
        idle_seconds: float,
        timeout_seconds: float = 300.0,
    ) -> BotIdleTimeoutReport:
        """Return idle timeout advisory.

        Args:
            bot_id: Non-empty bot id.
            idle_seconds: Seconds idle (``>= 0``).
            timeout_seconds: Eviction threshold (``> 0``).

        Returns:
            BotIdleTimeoutReport with ``requires_human_review=True``.
        """

        bid = bot_id.strip()
        if not bid:
            raise ValueError("bot_id must be non-empty")
        if idle_seconds < 0:
            raise ValueError("idle_seconds must be >= 0")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be > 0")

        if idle_seconds >= timeout_seconds:
            band = "evict"
        elif idle_seconds >= timeout_seconds * 0.7:
            band = "idle"
        else:
            band = "active"

        return BotIdleTimeoutReport(
            bot_id=bid,
            idle_seconds=float(idle_seconds),
            timeout_seconds=float(timeout_seconds),
            band=band,
            requires_human_review=True,
        )
