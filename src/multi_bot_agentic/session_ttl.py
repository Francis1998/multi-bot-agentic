"""Session TTL expirer with advisory or hard expiry.

Tracks idle timeout per ``session_id``; activity via ``touch`` resets the
deadline. Distinct from ``ConversationTurnBudgetGuard`` (turn counts) and
``RunDeadlineWatchdog`` (single wall-clock run deadline) — this is a thin,
stdlib-only per-session idle TTL for GPT-5.5 / Claude Sonnet 4.6 /
Gemini 3.x / Kimi K2 multi-bot chats. Fills a gap vs AutoGen/CrewAI/LangGraph,
which often bound graph steps or tokens without an explicit per-session idle
TTL with advisory vs hard modes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True)
class SessionTtlStatus:
    """Snapshot of a session's idle TTL.

    Attributes:
        session_id: Conversation / session identifier.
        ttl_seconds: Configured idle TTL.
        remaining_seconds: Seconds until expiry (negative when overdue).
        expired: True when ``now >= expires_at``.
        mode: ``advisory`` or ``hard``.
        last_activity_at: Last touch timestamp, or None when unseen.
        expires_at: Absolute expiry, or None when unseen.
    """

    session_id: str
    ttl_seconds: float
    remaining_seconds: float
    expired: bool
    mode: str
    last_activity_at: datetime | None
    expires_at: datetime | None


class SessionTtlExpirer:
    """Per-session idle TTL with advisory or hard enforcement.

    Caller-driven v1: ``touch`` on activity (resets deadline), ``check``
    before continuing, ``reset`` when a session ends. Never performs
    network I/O.
    """

    _VALID_MODES = frozenset({"advisory", "hard"})

    def __init__(self, *, ttl_seconds: float, mode: str = "advisory") -> None:
        """Create a session TTL expirer.

        Args:
            ttl_seconds: Positive idle TTL in seconds.
            mode: ``advisory`` (status only) or ``hard`` (raises when expired).

        Raises:
            ValueError: When ``ttl_seconds`` is not positive or ``mode`` is invalid.
        """

        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be > 0")
        normalized = mode.strip().lower()
        if normalized not in self._VALID_MODES:
            raise ValueError("mode must be 'advisory' or 'hard'")
        self._ttl_seconds = float(ttl_seconds)
        self._mode = normalized
        self._last_activity: dict[str, datetime] = {}

    @property
    def ttl_seconds(self) -> float:
        """Configured idle TTL in seconds."""

        return self._ttl_seconds

    @property
    def mode(self) -> str:
        """Enforcement mode (``advisory`` or ``hard``)."""

        return self._mode

    def touch(self, session_id: str, *, now: datetime | None = None) -> SessionTtlStatus:
        """Record activity for ``session_id`` (resets the idle deadline).

        In ``hard`` mode, raises if the session is already expired before
        touching (does not revive an expired session without ``reset``).

        Args:
            session_id: Session identifier (non-empty).
            now: Aware UTC timestamp (defaults to utcnow).

        Returns:
            SessionTtlStatus after the touch.

        Raises:
            ValueError: When ``session_id`` is empty or ``now`` is naive.
            RuntimeError: In hard mode when the session is already expired.
        """

        sid = self._require_session(session_id)
        moment = self._resolve_now(now)
        if sid in self._last_activity and self._mode == "hard":
            status = self._status(sid, moment)
            if status.expired:
                raise RuntimeError(
                    f"session TTL expired for session {sid!r}: remaining={status.remaining_seconds:.3f}s"
                )
        self._last_activity[sid] = moment
        return self._status(sid, moment)

    def check(self, session_id: str, *, now: datetime | None = None) -> SessionTtlStatus:
        """Return current TTL status without resetting activity.

        Args:
            session_id: Session identifier (non-empty).
            now: Aware UTC timestamp (defaults to utcnow).

        Returns:
            SessionTtlStatus (unseen sessions report expired=False with
            remaining_seconds equal to ttl_seconds and null activity stamps).

        Raises:
            ValueError: When ``session_id`` is empty or ``now`` is naive.
            RuntimeError: In hard mode when the session is expired.
        """

        sid = self._require_session(session_id)
        moment = self._resolve_now(now)
        status = self._status(sid, moment)
        if self._mode == "hard" and status.expired:
            raise RuntimeError(f"session TTL expired for session {sid!r}: remaining={status.remaining_seconds:.3f}s")
        return status

    def reset(self, session_id: str) -> bool:
        """Clear activity tracking for ``session_id``.

        Args:
            session_id: Session identifier (non-empty).

        Returns:
            True when a session was cleared; False on miss.

        Raises:
            ValueError: When ``session_id`` is empty.
        """

        sid = self._require_session(session_id)
        return self._last_activity.pop(sid, None) is not None

    def _status(self, session_id: str, now: datetime) -> SessionTtlStatus:
        last = self._last_activity.get(session_id)
        if last is None:
            return SessionTtlStatus(
                session_id=session_id,
                ttl_seconds=self._ttl_seconds,
                remaining_seconds=self._ttl_seconds,
                expired=False,
                mode=self._mode,
                last_activity_at=None,
                expires_at=None,
            )
        expires_at = last + timedelta(seconds=self._ttl_seconds)
        remaining = (expires_at - now).total_seconds()
        return SessionTtlStatus(
            session_id=session_id,
            ttl_seconds=self._ttl_seconds,
            remaining_seconds=remaining,
            expired=now >= expires_at,
            mode=self._mode,
            last_activity_at=last,
            expires_at=expires_at,
        )

    @staticmethod
    def _resolve_now(now: datetime | None) -> datetime:
        if now is None:
            return datetime.now(timezone.utc)
        if now.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        return now

    @staticmethod
    def _require_session(session_id: str) -> str:
        stripped = session_id.strip()
        if not stripped:
            raise ValueError("session_id must be non-empty")
        return stripped
