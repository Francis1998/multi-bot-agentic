"""ToolSandboxDiskQuota guard/advisor.

Flags disk_mb pressure with HITL bands. Distinct from
``ToolSandboxMemoryQuotaGuard`` and ``ToolSandboxCpuQuotaGuard``.
Fills a gap vs AutoGen/CrewAI/LangGraph tool-sandbox disk quota controls.
Works with frontier multi-LLM stacks. Never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolSandboxDiskQuotaStatus:
    """ToolSandboxDiskQuotaGuard status."""

    session_id: str
    disk_mb: float
    soft_limit: float
    hard_limit: float
    band: str
    requires_human_review: bool


class ToolSandboxDiskQuotaGuard:
    """Gate disk_mb vs soft/hard limits."""

    def __init__(self, *, soft_limit: float = 1024.0, hard_limit: float = 4096.0) -> None:
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

    def check(self, session_id: str, *, disk_mb: float) -> ToolSandboxDiskQuotaStatus:
        """Return band for observed disk_mb.

        Args:
            session_id: Non-empty id.
            disk_mb: Observed value (``>= 0``).

        Returns:
            ToolSandboxDiskQuotaStatus with ``requires_human_review=True``.
        """

        sid = session_id.strip()
        if not sid:
            raise ValueError("session_id must be non-empty")
        if disk_mb < 0:
            raise ValueError("disk_mb must be >= 0")

        if disk_mb <= self._soft:
            band = "ok"
        elif disk_mb <= self._hard:
            band = "elevated"
        else:
            band = "blocked"

        return ToolSandboxDiskQuotaStatus(
            session_id=sid,
            disk_mb=float(disk_mb),
            soft_limit=self._soft,
            hard_limit=self._hard,
            band=band,
            requires_human_review=True,
        )
