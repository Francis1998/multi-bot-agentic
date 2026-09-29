"""Tool invocation deadline guard.

Flags per-tool invocation elapsed time against a deadline budget with HITL
bands. Distinct from ``ToolCallLatencyTracker`` (latency stats) and
``RunDeadlineWatchdog`` (run-level deadline). Fills a gap vs AutoGen /
CrewAI / LangGraph per-tool invocation deadlines. Works with GPT-5.5 /
Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. Never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolInvocationDeadlineStatus:
    """Tool invocation deadline status."""

    session_id: str
    tool_name: str
    elapsed_s: float
    deadline_s: float
    ratio: float
    band: str
    requires_human_review: bool


class ToolInvocationDeadlineGuard:
    """Gate a single tool invocation against its deadline."""

    def check(
        self,
        session_id: str,
        *,
        tool_name: str,
        elapsed_s: float,
        deadline_s: float,
    ) -> ToolInvocationDeadlineStatus:
        """Return deadline band for one tool invocation.

        Args:
            session_id: Non-empty session id.
            tool_name: Non-empty tool name.
            elapsed_s: Elapsed seconds (``>= 0``).
            deadline_s: Deadline seconds (``> 0``).

        Returns:
            ToolInvocationDeadlineStatus with ``requires_human_review=True``.
        """

        sid = session_id.strip()
        name = tool_name.strip()
        if not sid:
            raise ValueError("session_id must be non-empty")
        if not name:
            raise ValueError("tool_name must be non-empty")
        if elapsed_s < 0:
            raise ValueError("elapsed_s must be >= 0")
        if deadline_s <= 0:
            raise ValueError("deadline_s must be > 0")

        ratio = round(elapsed_s / deadline_s, 4)
        if ratio >= 1.0:
            band = "expired"
        elif ratio >= 0.7:
            band = "approaching"
        else:
            band = "within_budget"

        return ToolInvocationDeadlineStatus(
            session_id=sid,
            tool_name=name,
            elapsed_s=float(elapsed_s),
            deadline_s=float(deadline_s),
            ratio=float(ratio),
            band=band,
            requires_human_review=True,
        )
