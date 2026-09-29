"""Critic timeout band guard.

Flags critic-pass waits that approach or exceed a timeout budget with HITL
bands. Distinct from ``CriticPassBudgetLimiter`` (pass count) and
``ConsensusTimeoutBandGuard`` (consensus wait). Fills a gap vs AutoGen /
CrewAI / LangGraph critic-pass timeouts. Works with GPT-5.5 /
Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. Never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CriticTimeoutStatus:
    """Critic timeout band status."""

    session_id: str
    waited_s: float
    timeout_s: float
    ratio: float
    band: str
    requires_human_review: bool


class CriticTimeoutBandGuard:
    """Gate critic-pass waits against a timeout budget."""

    def check(
        self,
        session_id: str,
        *,
        waited_s: float,
        timeout_s: float,
    ) -> CriticTimeoutStatus:
        """Return timeout band for a critic wait.

        Args:
            session_id: Non-empty session id.
            waited_s: Seconds already waiting (``>= 0``).
            timeout_s: Critic timeout seconds (``> 0``).

        Returns:
            CriticTimeoutStatus with ``requires_human_review=True``.
        """

        sid = session_id.strip()
        if not sid:
            raise ValueError("session_id must be non-empty")
        if waited_s < 0:
            raise ValueError("waited_s must be >= 0")
        if timeout_s <= 0:
            raise ValueError("timeout_s must be > 0")

        ratio = round(waited_s / timeout_s, 4)
        if ratio >= 1.0:
            band = "timed_out"
        elif ratio >= 0.7:
            band = "approaching"
        else:
            band = "within_budget"

        return CriticTimeoutStatus(
            session_id=sid,
            waited_s=float(waited_s),
            timeout_s=float(timeout_s),
            ratio=float(ratio),
            band=band,
            requires_human_review=True,
        )
