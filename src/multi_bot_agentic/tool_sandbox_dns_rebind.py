"""ToolSandboxDnsRebindGuard band guard.

Flags rebind_score pressure with HITL bands. Distinct from
`ToolSandboxNetworkExfilGuard` / `ToolSandboxEgressGuard`.
Fills a gap vs AutoGen/CrewAI/LangGraph tool-sandbox DNS-rebinding guards.
Works with frontier multi-LLM stacks. Never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolSandboxDnsRebindStatus:
    """ToolSandboxDnsRebindGuard status."""

    session_id: str
    rebind_score: float
    soft_limit: float
    hard_limit: float
    band: str
    requires_human_review: bool


class ToolSandboxDnsRebindGuard:
    """Gate rebind_score vs soft/hard limits."""

    def __init__(self, *, soft_limit: float = 0.2, hard_limit: float = 0.6) -> None:
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

    def check(self, session_id: str, *, rebind_score: float) -> ToolSandboxDnsRebindStatus:
        """Return band for observed rebind_score.

        Args:
            session_id: Non-empty id.
            rebind_score: Observed value (``>= 0``).

        Returns:
            ToolSandboxDnsRebindStatus with ``requires_human_review=True``.
        """

        sid = session_id.strip()
        if not sid:
            raise ValueError("session_id must be non-empty")
        if rebind_score < 0:
            raise ValueError("rebind_score must be >= 0")

        if rebind_score <= self._soft:
            band = "ok"
        elif rebind_score <= self._hard:
            band = "elevated"
        else:
            band = "blocked"

        return ToolSandboxDnsRebindStatus(
            session_id=sid,
            rebind_score=float(rebind_score),
            soft_limit=self._soft,
            hard_limit=self._hard,
            band=band,
            requires_human_review=True,
        )
