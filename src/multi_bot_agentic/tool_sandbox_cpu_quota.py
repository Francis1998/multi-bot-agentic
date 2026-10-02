"""Tool sandbox CPU quota guard.

Flags tool-sandbox CPU quota pressure with HITL bands. Distinct from
``ToolSandboxEgressClassGuard`` and ``ToolArgByteBudgetGuard``.
Fills a gap vs AutoGen/CrewAI/LangGraph tool-sandbox CPU quota controls.
Works with GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x /
Kimi K2. Never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolSandboxCpuQuotaStatus:
    """Tool sandbox CPU quota status."""

    session_id: str
    cpu_percent: float
    soft_limit: float
    hard_limit: float
    band: str
    requires_human_review: bool


class ToolSandboxCpuQuotaGuard:
    """Gate tool-sandbox CPU percent vs soft/hard limits."""

    def __init__(self, *, soft_limit: float = 70.0, hard_limit: float = 95.0) -> None:
        """Initialize CPU percent limits.

        Args:
            soft_limit: Soft max CPU percent (``> 0``).
            hard_limit: Hard max CPU percent (``> soft_limit``).
        """

        if soft_limit <= 0:
            raise ValueError("soft_limit must be > 0")
        if hard_limit <= soft_limit:
            raise ValueError("hard_limit must be > soft_limit")
        self._soft = soft_limit
        self._hard = hard_limit

    def check(self, session_id: str, *, cpu_percent: float) -> ToolSandboxCpuQuotaStatus:
        """Return CPU quota band.

        Args:
            session_id: Non-empty session id.
            cpu_percent: Observed sandbox CPU percent (``>= 0``).

        Returns:
            ToolSandboxCpuQuotaStatus with ``requires_human_review=True``.
        """

        sid = session_id.strip()
        if not sid:
            raise ValueError("session_id must be non-empty")
        if cpu_percent < 0:
            raise ValueError("cpu_percent must be >= 0")

        if cpu_percent <= self._soft:
            band = "ok"
        elif cpu_percent <= self._hard:
            band = "elevated"
        else:
            band = "blocked"

        return ToolSandboxCpuQuotaStatus(
            session_id=sid,
            cpu_percent=float(cpu_percent),
            soft_limit=self._soft,
            hard_limit=self._hard,
            band=band,
            requires_human_review=True,
        )
