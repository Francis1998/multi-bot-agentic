"""Conversation turn budget guard for multi-bot sessions.

Caps the number of turns per ``session_id`` with advisory or hard gating.
Distinct from ``BudgetedStepPlanner`` (token/step preflight) and
``RunDeadlineWatchdog`` (wall-clock) — this is a thin, stdlib-only
conversation-turn counter for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x /
Kimi K2 multi-bot chats. Fills a gap vs AutoGen/CrewAI/LangGraph, which
often bound graph steps or tokens without an explicit per-session turn
budget with advisory vs hard modes.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TurnBudgetStatus:
    """Snapshot of a session's turn budget.

    Attributes:
        session_id: Conversation / session identifier.
        turn_count: Turns recorded so far.
        max_turns: Configured maximum turns.
        remaining: Turns still available (``max(0, max_turns - turn_count)``).
        exhausted: True when ``turn_count >= max_turns``.
        mode: ``advisory`` or ``hard``.
    """

    session_id: str
    turn_count: int
    max_turns: int
    remaining: int
    exhausted: bool
    mode: str


class ConversationTurnBudgetGuard:
    """Max-turns-per-session guard with advisory or hard enforcement.

    Caller-driven v1: ``record_turn`` after each user/agent exchange,
    ``check`` before starting the next turn, ``reset`` when a session ends.
    Never performs network I/O.
    """

    _VALID_MODES = frozenset({"advisory", "hard"})

    def __init__(self, *, max_turns: int, mode: str = "advisory") -> None:
        """Create a turn budget guard.

        Args:
            max_turns: Positive maximum turns per session.
            mode: ``advisory`` (status only) or ``hard`` (raises on overflow).

        Raises:
            ValueError: When ``max_turns`` is not positive or ``mode`` is invalid.
        """

        if max_turns < 1:
            raise ValueError("max_turns must be >= 1")
        normalized = mode.strip().lower()
        if normalized not in self._VALID_MODES:
            raise ValueError("mode must be 'advisory' or 'hard'")
        self._max_turns = int(max_turns)
        self._mode = normalized
        self._counts: dict[str, int] = {}

    @property
    def max_turns(self) -> int:
        """Configured maximum turns per session."""

        return self._max_turns

    @property
    def mode(self) -> str:
        """Enforcement mode (``advisory`` or ``hard``)."""

        return self._mode

    def record_turn(self, session_id: str) -> TurnBudgetStatus:
        """Increment the turn counter for ``session_id`` and return status.

        In ``hard`` mode, raises if the session is already exhausted before
        recording (does not increment past the cap).

        Args:
            session_id: Session identifier (non-empty).

        Returns:
            TurnBudgetStatus after the recorded turn.

        Raises:
            ValueError: When ``session_id`` is empty.
            RuntimeError: In hard mode when the budget is already exhausted.
        """

        sid = self._require_session(session_id)
        current = self._counts.get(sid, 0)
        if self._mode == "hard" and current >= self._max_turns:
            raise RuntimeError(
                f"turn budget exhausted for session {sid!r}: "
                f"{current}/{self._max_turns}"
            )
        self._counts[sid] = current + 1
        return self._status(sid)

    def check(self, session_id: str) -> TurnBudgetStatus:
        """Return current budget status without incrementing.

        Args:
            session_id: Session identifier (non-empty).

        Returns:
            TurnBudgetStatus for the session (zero turns if unseen).

        Raises:
            ValueError: When ``session_id`` is empty.
        """

        sid = self._require_session(session_id)
        return self._status(sid)

    def reset(self, session_id: str) -> bool:
        """Clear the turn counter for ``session_id``.

        Args:
            session_id: Session identifier (non-empty).

        Returns:
            True when a counter was cleared; False on miss.

        Raises:
            ValueError: When ``session_id`` is empty.
        """

        sid = self._require_session(session_id)
        return self._counts.pop(sid, None) is not None

    def _status(self, session_id: str) -> TurnBudgetStatus:
        count = self._counts.get(session_id, 0)
        remaining = max(0, self._max_turns - count)
        return TurnBudgetStatus(
            session_id=session_id,
            turn_count=count,
            max_turns=self._max_turns,
            remaining=remaining,
            exhausted=count >= self._max_turns,
            mode=self._mode,
        )

    @staticmethod
    def _require_session(session_id: str) -> str:
        stripped = session_id.strip()
        if not stripped:
            raise ValueError("session_id must be non-empty")
        return stripped
