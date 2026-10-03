"""ToolSandboxMemoryQuota guard.

Flags memory mb pressure with HITL bands. Distinct from
``ToolSandboxCpuQuotaGuard and SharedMemoryQuotaGuard``.
Fills a gap vs AutoGen/CrewAI/LangGraph tool-sandbox memory quota controls.
Works with GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x /
Kimi K2. Never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolSandboxMemoryQuotaStatus:
    """ToolSandboxMemoryQuotaGuard status."""

    session_id: str
    memory_mb: float
    soft_limit: float
    hard_limit: float
    band: str
    requires_human_review: bool


class ToolSandboxMemoryQuotaGuard:
    """Gate memory mb vs soft/hard limits."""

    def __init__(self, *, soft_limit: float = 512.0, hard_limit: float = 1024.0) -> None:
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

    def check(self, session_id: str, *, memory_mb: float) -> ToolSandboxMemoryQuotaStatus:
        """Return band for observed memory_mb.

        Args:
            session_id: Non-empty id.
            memory_mb: Observed value (``>= 0``).

        Returns:
            ToolSandboxMemoryQuotaStatus with ``requires_human_review=True``.
        """

        sid = session_id.strip()
        if not sid:
            raise ValueError("session_id must be non-empty")
        if memory_mb < 0:
            raise ValueError("memory_mb must be >= 0")

        if memory_mb <= self._soft:
            band = "ok"
        elif memory_mb <= self._hard:
            band = "elevated"
        else:
            band = "blocked"

        return ToolSandboxMemoryQuotaStatus(
            session_id=sid,
            memory_mb=float(memory_mb),
            soft_limit=self._soft,
            hard_limit=self._hard,
            band=band,
            requires_human_review=True,
        )
