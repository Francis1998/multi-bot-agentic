"""Per-tool call quota guard for multi-bot sessions.

Caps how many times each tool may be invoked per ``session_id`` with
advisory or hard deny after N calls. Distinct from ``ToolPermissionAllowlist``
(ACL allow/deny by bot) and ``ToolCallLatencyTracker`` (latency samples) —
this is a thin, stdlib-only per-session per-tool call counter for GPT-5.5 /
Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 multi-bot crews. Fills a gap vs
AutoGen/CrewAI/LangGraph/Semantic Kernel, which often rate-limit by wall
clock or share one global tool budget without an explicit per-session
per-tool quota with advisory vs hard modes. Never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolCallQuotaStatus:
    """Snapshot of a session/tool call quota.

    Attributes:
        session_id: Conversation / session identifier.
        tool_name: Tool under consideration.
        call_count: Calls recorded so far for this pair.
        max_calls: Configured maximum calls.
        remaining: Calls still available (``max(0, max_calls - call_count)``).
        exhausted: True when ``call_count >= max_calls``.
        mode: ``advisory`` or ``hard``.
        allowed: True when the next call is permitted under the mode.
    """

    session_id: str
    tool_name: str
    call_count: int
    max_calls: int
    remaining: int
    exhausted: bool
    mode: str
    allowed: bool


class ToolCallQuotaGuard:
    """Per-tool call quota per session with advisory or hard deny.

    Caller-driven v1: ``check`` before execute, ``record`` after a call,
    ``reset`` when a session ends or quotas should clear. Never performs
    network I/O.
    """

    _VALID_MODES = frozenset({"advisory", "hard"})

    def __init__(self, *, max_calls: int, mode: str = "advisory") -> None:
        """Create a per-tool call quota guard.

        Args:
            max_calls: Positive maximum calls per session per tool.
            mode: ``advisory`` (status only; always allows) or ``hard``
                (denies / raises when exhausted).

        Raises:
            ValueError: When ``max_calls`` is not positive or ``mode`` is invalid.
        """

        if max_calls < 1:
            raise ValueError("max_calls must be >= 1")
        normalized = mode.strip().lower()
        if normalized not in self._VALID_MODES:
            raise ValueError("mode must be 'advisory' or 'hard'")
        self._max_calls = int(max_calls)
        self._mode = normalized
        self._counts: dict[tuple[str, str], int] = {}

    @property
    def max_calls(self) -> int:
        """Configured maximum calls per session per tool."""

        return self._max_calls

    @property
    def mode(self) -> str:
        """Enforcement mode (``advisory`` or ``hard``)."""

        return self._mode

    def record(self, session_id: str, tool_name: str) -> ToolCallQuotaStatus:
        """Increment the call counter for ``session_id`` / ``tool_name``.

        In ``hard`` mode, raises if the quota is already exhausted before
        recording (does not increment past the cap).

        Args:
            session_id: Session identifier (non-empty).
            tool_name: Tool identifier (non-empty).

        Returns:
            ToolCallQuotaStatus after the recorded call.

        Raises:
            ValueError: When ``session_id`` or ``tool_name`` is empty.
            RuntimeError: In hard mode when the quota is already exhausted.
        """

        sid = self._require_id(session_id, "session_id")
        tool = self._require_id(tool_name, "tool_name")
        key = (sid, tool)
        current = self._counts.get(key, 0)
        if self._mode == "hard" and current >= self._max_calls:
            raise RuntimeError(
                f"tool call quota exhausted for session {sid!r} tool {tool!r}: {current}/{self._max_calls}"
            )
        self._counts[key] = current + 1
        return self._status(sid, tool)

    def check(self, session_id: str, tool_name: str) -> ToolCallQuotaStatus:
        """Return current quota status without incrementing.

        Args:
            session_id: Session identifier (non-empty).
            tool_name: Tool identifier (non-empty).

        Returns:
            ToolCallQuotaStatus (zero calls if unseen).

        Raises:
            ValueError: When ``session_id`` or ``tool_name`` is empty.
        """

        sid = self._require_id(session_id, "session_id")
        tool = self._require_id(tool_name, "tool_name")
        return self._status(sid, tool)

    def reset(self, session_id: str, tool_name: str | None = None) -> bool:
        """Clear counters for ``session_id`` (one tool or all tools).

        Args:
            session_id: Session identifier (non-empty).
            tool_name: Optional tool to clear; when None, clears all tools
                for the session.

        Returns:
            True when any counter was cleared; False on miss.

        Raises:
            ValueError: When ``session_id`` is empty or ``tool_name`` is empty.
        """

        sid = self._require_id(session_id, "session_id")
        if tool_name is not None:
            tool = self._require_id(tool_name, "tool_name")
            return self._counts.pop((sid, tool), None) is not None
        keys = [key for key in self._counts if key[0] == sid]
        for key in keys:
            del self._counts[key]
        return bool(keys)

    def _status(self, session_id: str, tool_name: str) -> ToolCallQuotaStatus:
        count = self._counts.get((session_id, tool_name), 0)
        remaining = max(0, self._max_calls - count)
        exhausted = count >= self._max_calls
        # advisory always allows; hard allows only when not exhausted
        allowed = True if self._mode == "advisory" else not exhausted
        return ToolCallQuotaStatus(
            session_id=session_id,
            tool_name=tool_name,
            call_count=count,
            max_calls=self._max_calls,
            remaining=remaining,
            exhausted=exhausted,
            mode=self._mode,
            allowed=allowed,
        )

    @staticmethod
    def _require_id(value: str, label: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError(f"{label} must be non-empty")
        return stripped
