"""Bot heartbeat liveness watchdog for multi-bot sessions.

Tracks last-heartbeat timestamps per bot and reports stale/alive status.
Distinct from ``SessionTtlExpirer`` (session idle TTL) and
``RunDeadlineWatchdog`` (wall-clock run deadline). Fills a gap vs AutoGen /
CrewAI / LangGraph runtimes that often lack explicit per-bot heartbeat
liveness. Works with GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2.
Never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class BotHeartbeatStatus:
    """Liveness status for one bot in a session.

    Attributes:
        session_id: Conversation / session identifier.
        bot_id: Bot identifier.
        age_seconds: Seconds since last heartbeat.
        stale: True when age >= timeout.
        band: ``alive``, ``stale``, or ``unknown``.
    """

    session_id: str
    bot_id: str
    age_seconds: float | None
    stale: bool
    band: str


class BotHeartbeatLivenessWatchdog:
    """Track bot heartbeats and flag stale bots."""

    def __init__(self, *, timeout_seconds: float = 30.0) -> None:
        """Create a heartbeat watchdog.

        Args:
            timeout_seconds: Stale threshold in seconds (must be > 0).

        Raises:
            ValueError: When timeout_seconds <= 0.
        """

        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be > 0")
        self._timeout = float(timeout_seconds)
        self._beats: dict[tuple[str, str], datetime] = {}

    @property
    def timeout_seconds(self) -> float:
        """Return configured stale timeout."""

        return self._timeout

    def heartbeat(
        self,
        session_id: str,
        bot_id: str,
        *,
        now: datetime | None = None,
    ) -> BotHeartbeatStatus:
        """Record a heartbeat and return alive status.

        Args:
            session_id: Non-empty session id.
            bot_id: Non-empty bot id.
            now: Optional clock override (UTC-aware preferred).

        Returns:
            BotHeartbeatStatus with band ``alive``.
        """

        sid, bid = self._ids(session_id, bot_id)
        stamp = self._stamp(now)
        self._beats[(sid, bid)] = stamp
        return BotHeartbeatStatus(
            session_id=sid,
            bot_id=bid,
            age_seconds=0.0,
            stale=False,
            band="alive",
        )

    def status(
        self,
        session_id: str,
        bot_id: str,
        *,
        now: datetime | None = None,
    ) -> BotHeartbeatStatus:
        """Return current liveness for a bot.

        Returns:
            Status with band ``alive`` / ``stale`` / ``unknown``.
        """

        sid, bid = self._ids(session_id, bot_id)
        stamp = self._beats.get((sid, bid))
        if stamp is None:
            return BotHeartbeatStatus(
                session_id=sid,
                bot_id=bid,
                age_seconds=None,
                stale=True,
                band="unknown",
            )
        current = self._stamp(now)
        age = max(0.0, (current - stamp).total_seconds())
        stale = age >= self._timeout
        return BotHeartbeatStatus(
            session_id=sid,
            bot_id=bid,
            age_seconds=age,
            stale=stale,
            band="stale" if stale else "alive",
        )

    def stale_bots(
        self,
        session_id: str,
        *,
        now: datetime | None = None,
    ) -> tuple[str, ...]:
        """Return sorted bot ids that are stale in ``session_id``."""

        sid = session_id.strip()
        if not sid:
            raise ValueError("session_id must be non-empty")
        current = self._stamp(now)
        out: list[str] = []
        for (s, b), stamp in self._beats.items():
            if s != sid:
                continue
            age = (current - stamp).total_seconds()
            if age >= self._timeout:
                out.append(b)
        return tuple(sorted(out))

    @staticmethod
    def _ids(session_id: str, bot_id: str) -> tuple[str, str]:
        sid = session_id.strip()
        bid = bot_id.strip()
        if not sid:
            raise ValueError("session_id must be non-empty")
        if not bid:
            raise ValueError("bot_id must be non-empty")
        return sid, bid

    @staticmethod
    def _stamp(now: datetime | None) -> datetime:
        stamp = now or datetime.now(timezone.utc)
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        return stamp
