"""ToolSandboxSyscallDenylistGuard band guard.

Flags denied_syscall_rate pressure with HITL bands. Distinct from
`ToolSandboxEgressGuard` / `ToolSandboxNetworkExfilGuard`.
Fills a gap vs AutoGen/CrewAI/LangGraph tool-sandbox syscall denylist guards.
Works with frontier multi-LLM stacks. Never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolSandboxSyscallDenylistStatus:
    """ToolSandboxSyscallDenylistGuard status."""

    session_id: str
    denied_syscall_rate: float
    soft_limit: float
    hard_limit: float
    band: str
    requires_human_review: bool


class ToolSandboxSyscallDenylistGuard:
    """Gate denied_syscall_rate vs soft/hard limits."""

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

    def check(self, session_id: str, *, denied_syscall_rate: float) -> ToolSandboxSyscallDenylistStatus:
        """Return band for observed denied_syscall_rate.

        Args:
            session_id: Non-empty id.
            denied_syscall_rate: Observed value (>= 0).

        Returns:
            ToolSandboxSyscallDenylistStatus with ``requires_human_review=True``.
        """

        sid = session_id.strip()
        if not sid:
            raise ValueError("session_id must be non-empty")
        if denied_syscall_rate < 0:
            raise ValueError("denied_syscall_rate must be >= 0")

        if denied_syscall_rate <= self._soft:
            band = "ok"
        elif denied_syscall_rate <= self._hard:
            band = "elevated"
        else:
            band = "blocked"

        return ToolSandboxSyscallDenylistStatus(
            session_id=sid,
            denied_syscall_rate=float(denied_syscall_rate),
            soft_limit=self._soft,
            hard_limit=self._hard,
            band=band,
            requires_human_review=True,
        )
