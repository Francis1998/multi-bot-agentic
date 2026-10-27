"""ToolSandboxEscapeAttemptBandAdvisor band guard.

Flags attempt_ratio pressure with HITL bands. Distinct from
`ToolResultSchemaDriftBandAdvisor` / `ToolPermissionEscalationBandAdvisor`.
Fills a gap vs LangGraph/CrewAI/AutoGen tool sandbox-escape attempt monitors.
Works with frontier multi-LLM stacks. Never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolSandboxEscapeAttemptStatus:
    """ToolSandboxEscapeAttemptBandAdvisor status."""

    session_id: str
    attempt_ratio: float
    soft_limit: float
    hard_limit: float
    band: str
    requires_human_review: bool


class ToolSandboxEscapeAttemptBandAdvisor:
    """Gate attempt_ratio vs soft/hard limits."""

    def __init__(self, *, soft_limit: float = 0.05, hard_limit: float = 0.2) -> None:
        """Initialize limits.

        Args:
            soft_limit: Soft max (> 0).
            hard_limit: Hard max (> soft_limit).
        """

        if soft_limit <= 0:
            raise ValueError("soft_limit must be > 0")
        if hard_limit <= soft_limit:
            raise ValueError("hard_limit must be > soft_limit")
        self._soft = soft_limit
        self._hard = hard_limit

    def advise(self, session_id: str, *, attempt_ratio: float) -> ToolSandboxEscapeAttemptStatus:
        """Return band for observed attempt_ratio.

        Args:
            session_id: Non-empty id.
            attempt_ratio: Observed value (>= 0).

        Returns:
            ToolSandboxEscapeAttemptStatus with ``requires_human_review=True``.
        """

        sid = session_id.strip()
        if not sid:
            raise ValueError("session_id must be non-empty")
        if attempt_ratio < 0:
            raise ValueError("attempt_ratio must be >= 0")

        if attempt_ratio <= self._soft:
            band = "ok"
        elif attempt_ratio <= self._hard:
            band = "elevated"
        else:
            band = "blocked"

        return ToolSandboxEscapeAttemptStatus(
            session_id=sid,
            attempt_ratio=float(attempt_ratio),
            soft_limit=self._soft,
            hard_limit=self._hard,
            band=band,
            requires_human_review=True,
        )
