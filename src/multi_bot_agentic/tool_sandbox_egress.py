"""Tool sandbox egress class guard.

Classifies tool sandbox egress risk (none/local/network/admin) with HITL bands.
Distinct from ``ToolPermissionAllowlist`` (allowlist) and
``ToolInvocationDeadlineGuard`` (deadline). Fills a gap vs AutoGen /
CrewAI / LangGraph tool sandbox egress class controls.
Works with GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2.
Never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass

_RANK = {"none": 0, "local": 1, "network": 2, "admin": 3}


@dataclass(frozen=True)
class ToolSandboxEgressClassStatus:
    """Tool sandbox egress class status."""

    session_id: str
    tool_name: str
    egress_class: str
    max_allowed: str
    band: str
    requires_human_review: bool


class ToolSandboxEgressClassGuard:
    """Gate tool sandbox egress class vs a max allowed class."""

    def __init__(self, *, max_allowed: str = "local") -> None:
        """Initialize max allowed egress class.

        Args:
            max_allowed: One of ``none`` / ``local`` / ``network`` / ``admin``.
        """

        key = max_allowed.strip().lower()
        if key not in _RANK:
            raise ValueError("max_allowed must be none|local|network|admin")
        self._max = key

    def check(
        self,
        session_id: str,
        *,
        tool_name: str,
        egress_class: str,
    ) -> ToolSandboxEgressClassStatus:
        """Return egress band for one tool invocation.

        Args:
            session_id: Non-empty session id.
            tool_name: Non-empty tool name.
            egress_class: Declared egress class.

        Returns:
            ToolSandboxEgressClassStatus with ``requires_human_review=True``.
        """

        sid = session_id.strip()
        name = tool_name.strip()
        klass = egress_class.strip().lower()
        if not sid:
            raise ValueError("session_id must be non-empty")
        if not name:
            raise ValueError("tool_name must be non-empty")
        if klass not in _RANK:
            raise ValueError("egress_class must be none|local|network|admin")

        if _RANK[klass] <= _RANK[self._max]:
            band = "allowed"
        elif _RANK[klass] == _RANK[self._max] + 1:
            band = "elevated"
        else:
            band = "blocked"

        return ToolSandboxEgressClassStatus(
            session_id=sid,
            tool_name=name,
            egress_class=klass,
            max_allowed=self._max,
            band=band,
            requires_human_review=True,
        )
