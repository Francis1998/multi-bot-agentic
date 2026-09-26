"""Orchestrator stall watchdog.

Detects stalled orchestrator loops from seconds-since-progress and emits
HITL bands. Distinct from ``BotHeartbeatLivenessWatchdog`` (bot heartbeats)
and ``BotIdleTimeoutEvictor`` (idle eviction). Fills a gap vs AutoGen /
CrewAI / LangGraph stuck-orchestrator detection. Works with GPT-5.5 /
Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. Never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OrchestratorStallStatus:
    """Orchestrator stall status."""

    session_id: str
    seconds_since_progress: float
    warn_after_s: float
    stall_after_s: float
    band: str
    requires_human_review: bool


class OrchestratorStallWatchdog:
    """Flag stalled orchestrator sessions from idle progress timers."""

    def check(
        self,
        session_id: str,
        *,
        seconds_since_progress: float,
        warn_after_s: float = 30.0,
        stall_after_s: float = 120.0,
    ) -> OrchestratorStallStatus:
        """Return stall band for an orchestrator session.

        Args:
            session_id: Non-empty session id.
            seconds_since_progress: Seconds since last progress (``>= 0``).
            warn_after_s: Warn threshold seconds (``> 0``).
            stall_after_s: Stall threshold seconds (``>= warn_after_s``).

        Returns:
            OrchestratorStallStatus with ``requires_human_review=True``.
        """

        sid = session_id.strip()
        if not sid:
            raise ValueError("session_id must be non-empty")
        if seconds_since_progress < 0:
            raise ValueError("seconds_since_progress must be >= 0")
        if warn_after_s <= 0:
            raise ValueError("warn_after_s must be > 0")
        if stall_after_s < warn_after_s:
            raise ValueError("stall_after_s must be >= warn_after_s")

        if seconds_since_progress >= stall_after_s:
            band = "stalled"
        elif seconds_since_progress >= warn_after_s:
            band = "warning"
        else:
            band = "healthy"

        return OrchestratorStallStatus(
            session_id=sid,
            seconds_since_progress=float(seconds_since_progress),
            warn_after_s=float(warn_after_s),
            stall_after_s=float(stall_after_s),
            band=band,
            requires_human_review=True,
        )
