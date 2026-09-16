"""Session token budget ledger for cumulative per-session usage.

Tracks soft/hard cumulative token budgets per ``session_id`` with status
``ok`` / ``soft`` / ``hard``. Distinct from ``ConversationTurnBudgetGuard``
(turn counts) and ``RunDeadlineWatchdog`` (wall-clock) — this is a thin,
stdlib-only cumulative token ledger for GPT-5.5 / Claude Sonnet 4.6 /
Gemini 3.x / Kimi K2 multi-bot chats. Fills a gap vs AutoGen/CrewAI/LangGraph/
Semantic Kernel, which often bound graph steps or single-call tokens without
an explicit per-session soft/hard cumulative token ledger that never kills
processes.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SessionTokenBudgetStatus:
    """Snapshot of a session's cumulative token budget.

    Attributes:
        session_id: Conversation / session identifier.
        prompt_tokens: Cumulative prompt tokens recorded.
        completion_tokens: Cumulative completion tokens recorded.
        total_tokens: ``prompt_tokens + completion_tokens``.
        soft_limit: Soft threshold (status becomes ``soft`` at/above).
        hard_limit: Hard threshold (status becomes ``hard`` at/above).
        status: ``ok``, ``soft``, or ``hard``.
        remaining_to_hard: Tokens remaining until hard limit (``max(0, ...)``).
    """

    session_id: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    soft_limit: int
    hard_limit: int
    status: str
    remaining_to_hard: int


class SessionTokenBudgetLedger:
    """Soft/hard cumulative token budget per session (never kills processes).

    Caller-driven v1: ``record`` after each LLM exchange, ``check`` before the
    next call, ``reset`` when a session ends. Reports ``ok`` / ``soft`` /
    ``hard`` status only — never raises to terminate processes or network I/O.
    """

    _VALID_STATUSES = frozenset({"ok", "soft", "hard"})

    def __init__(self, *, soft_limit: int, hard_limit: int) -> None:
        """Create a session token budget ledger.

        Args:
            soft_limit: Positive soft threshold (must be ``<= hard_limit``).
            hard_limit: Positive hard threshold (must be ``>= soft_limit``).

        Raises:
            ValueError: When limits are not positive or soft > hard.
        """

        if soft_limit < 1:
            raise ValueError("soft_limit must be >= 1")
        if hard_limit < 1:
            raise ValueError("hard_limit must be >= 1")
        if soft_limit > hard_limit:
            raise ValueError("soft_limit must be <= hard_limit")
        self._soft_limit = int(soft_limit)
        self._hard_limit = int(hard_limit)
        self._prompt: dict[str, int] = {}
        self._completion: dict[str, int] = {}

    @property
    def soft_limit(self) -> int:
        """Configured soft token threshold."""

        return self._soft_limit

    @property
    def hard_limit(self) -> int:
        """Configured hard token threshold."""

        return self._hard_limit

    def record(
        self,
        session_id: str,
        *,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> SessionTokenBudgetStatus:
        """Add token usage for ``session_id`` and return status.

        Always records (never blocks or kills). Status reflects soft/hard
        thresholds after the update.

        Args:
            session_id: Session identifier (non-empty).
            prompt_tokens: Non-negative prompt tokens to add.
            completion_tokens: Non-negative completion tokens to add.

        Returns:
            SessionTokenBudgetStatus after recording.

        Raises:
            ValueError: When ``session_id`` is empty or token counts are negative.
        """

        sid = self._require_session(session_id)
        if prompt_tokens < 0:
            raise ValueError("prompt_tokens must be >= 0")
        if completion_tokens < 0:
            raise ValueError("completion_tokens must be >= 0")
        self._prompt[sid] = self._prompt.get(sid, 0) + int(prompt_tokens)
        self._completion[sid] = self._completion.get(sid, 0) + int(completion_tokens)
        return self._status(sid)

    def check(self, session_id: str) -> SessionTokenBudgetStatus:
        """Return current budget status without recording.

        Args:
            session_id: Session identifier (non-empty).

        Returns:
            SessionTokenBudgetStatus (zeros if unseen).

        Raises:
            ValueError: When ``session_id`` is empty.
        """

        sid = self._require_session(session_id)
        return self._status(sid)

    def reset(self, session_id: str) -> bool:
        """Clear cumulative counters for ``session_id``.

        Args:
            session_id: Session identifier (non-empty).

        Returns:
            True when counters were cleared; False on miss.

        Raises:
            ValueError: When ``session_id`` is empty.
        """

        sid = self._require_session(session_id)
        had = sid in self._prompt or sid in self._completion
        self._prompt.pop(sid, None)
        self._completion.pop(sid, None)
        return had

    def _status(self, session_id: str) -> SessionTokenBudgetStatus:
        prompt = self._prompt.get(session_id, 0)
        completion = self._completion.get(session_id, 0)
        total = prompt + completion
        if total >= self._hard_limit:
            status = "hard"
        elif total >= self._soft_limit:
            status = "soft"
        else:
            status = "ok"
        return SessionTokenBudgetStatus(
            session_id=session_id,
            prompt_tokens=prompt,
            completion_tokens=completion,
            total_tokens=total,
            soft_limit=self._soft_limit,
            hard_limit=self._hard_limit,
            status=status,
            remaining_to_hard=max(0, self._hard_limit - total),
        )

    @staticmethod
    def _require_session(session_id: str) -> str:
        stripped = session_id.strip()
        if not stripped:
            raise ValueError("session_id must be non-empty")
        return stripped
