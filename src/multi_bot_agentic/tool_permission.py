"""Per-bot tool permission allowlist for multi-bot ACL gates.

Gates tool calls by ``bot_id`` so each bot only invokes tools it was
explicitly granted. Distinct from the global ``SafetyPolicy`` tool allowlist
(run-wide) and from ``HitlApprovalGate`` (human review) — this is a thin,
stdlib-only per-bot ACL for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x /
Kimi K2 multi-bot crews. Fills a gap vs AutoGen/CrewAI/LangGraph, which
often share one tool set across agents without per-bot allow/deny checks.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ToolPermissionDecision(str, Enum):
    """Outcome of a per-bot tool permission check.

    Note:
        Exposed as ``(str, Enum)`` so Python 3.10 CI stays green (``StrEnum`` is 3.11+).
    """

    ALLOWED = "allowed"
    DENIED = "denied"


@dataclass(frozen=True)
class ToolPermissionResult:
    """Immutable result of checking whether a bot may call a tool.

    Attributes:
        bot_id: Bot that requested the tool.
        tool_name: Tool under consideration.
        decision: Allowed or denied.
        reason: Human-readable explanation of the decision.
    """

    bot_id: str
    tool_name: str
    decision: ToolPermissionDecision
    reason: str


class ToolPermissionAllowlist:
    """Per-bot tool ACL gate (default-deny unless granted).

    Caller-driven v1: ``grant`` tools to a bot, ``check`` before execute,
    ``revoke`` when scope should shrink. Never performs network I/O.
    """

    def __init__(self, *, default_deny: bool = True) -> None:
        """Create an empty per-bot allowlist.

        Args:
            default_deny: When True (default), unknown grants are denied.
                When False, bots without grants are allowed (still tracks
                explicit revokes via an empty grant set).

        Raises:
            ValueError: Not raised today; reserved for future bound checks.
        """

        self._default_deny = bool(default_deny)
        self._grants: dict[str, set[str]] = {}

    def grant(self, bot_id: str, tool_name: str) -> None:
        """Allow ``bot_id`` to call ``tool_name``.

        Args:
            bot_id: Bot identifier (non-empty).
            tool_name: Tool identifier (non-empty).

        Raises:
            ValueError: When ``bot_id`` or ``tool_name`` is empty.
        """

        bid = self._require_id(bot_id, "bot_id")
        tool = self._require_id(tool_name, "tool_name")
        self._grants.setdefault(bid, set()).add(tool)

    def revoke(self, bot_id: str, tool_name: str) -> bool:
        """Remove a prior grant for ``bot_id`` / ``tool_name``.

        Args:
            bot_id: Bot identifier (non-empty).
            tool_name: Tool identifier (non-empty).

        Returns:
            True when a grant was removed; False on miss.

        Raises:
            ValueError: When ``bot_id`` or ``tool_name`` is empty.
        """

        bid = self._require_id(bot_id, "bot_id")
        tool = self._require_id(tool_name, "tool_name")
        tools = self._grants.get(bid)
        if not tools or tool not in tools:
            return False
        tools.remove(tool)
        if not tools:
            del self._grants[bid]
        return True

    def check(self, bot_id: str, tool_name: str) -> ToolPermissionResult:
        """Return whether ``bot_id`` may call ``tool_name``.

        Args:
            bot_id: Bot identifier (non-empty).
            tool_name: Tool identifier (non-empty).

        Returns:
            ToolPermissionResult with decision and reason.

        Raises:
            ValueError: When ``bot_id`` or ``tool_name`` is empty.
        """

        bid = self._require_id(bot_id, "bot_id")
        tool = self._require_id(tool_name, "tool_name")
        tools = self._grants.get(bid)
        if tools is not None and tool in tools:
            return ToolPermissionResult(
                bot_id=bid,
                tool_name=tool,
                decision=ToolPermissionDecision.ALLOWED,
                reason="explicit grant",
            )
        if self._default_deny or tools is not None:
            reason = (
                "tool not in bot allowlist"
                if tools is not None
                else "default deny (no grants for bot)"
            )
            return ToolPermissionResult(
                bot_id=bid,
                tool_name=tool,
                decision=ToolPermissionDecision.DENIED,
                reason=reason,
            )
        return ToolPermissionResult(
            bot_id=bid,
            tool_name=tool,
            decision=ToolPermissionDecision.ALLOWED,
            reason="default allow (no grants recorded)",
        )

    def grants_for(self, bot_id: str) -> frozenset[str]:
        """Return the granted tool set for ``bot_id``.

        Args:
            bot_id: Bot identifier (non-empty).

        Returns:
            Frozen set of tool names (empty when none).

        Raises:
            ValueError: When ``bot_id`` is empty.
        """

        bid = self._require_id(bot_id, "bot_id")
        return frozenset(self._grants.get(bid, ()))

    @staticmethod
    def _require_id(value: str, label: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError(f"{label} must be non-empty")
        return stripped
