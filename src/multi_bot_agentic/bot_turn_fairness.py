"""Bot turn fairness scheduler for multi-bot crews.

Tracks how many turns each ``bot_id`` has taken in a session and recommends
the least-served eligible bot so one agent does not monopolize the loop.
Distinct from ``BotSkillTagRouter`` (skill-tag overlap routing) and
``StickyBotAffinityStore`` (session→bot pin). Fills a gap vs AutoGen / CrewAI /
LangGraph / Semantic Kernel, which often lack an explicit per-session turn
fairness scheduler with advisory vs hard modes. Works with GPT-5.5 /
Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 multi-bot crews. Never network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FairnessSnapshot:
    """Snapshot of per-bot turn counts for a session.

    Attributes:
        session_id: Conversation / session identifier.
        counts: Mapping of bot_id → turns taken.
        recommended_bot_id: Least-served eligible bot (tie: lexicographic).
        max_skew: Difference between max and min counts among eligible bots.
        mode: ``advisory`` or ``hard``.
        allowed: True when the next turn is permitted under the mode.
    """

    session_id: str
    counts: dict[str, int]
    recommended_bot_id: str | None
    max_skew: int
    mode: str
    allowed: bool


class BotTurnFairnessScheduler:
    """Recommend least-served bots and optionally cap turn skew.

    Caller-driven v1: ``recommend`` before assigning a turn, ``record`` after
    a bot speaks, ``reset`` when a session ends. Never performs network I/O.
    """

    _VALID_MODES = frozenset({"advisory", "hard"})

    def __init__(self, *, max_skew: int = 2, mode: str = "advisory") -> None:
        """Create a turn fairness scheduler.

        Args:
            max_skew: Maximum allowed (max_count - min_count) among eligible
                bots before hard mode denies further turns for over-served bots.
            mode: ``advisory`` (always allows; still recommends) or ``hard``
                (denies recording for bots that would exceed max_skew).

        Raises:
            ValueError: When ``max_skew`` < 0 or ``mode`` is invalid.
        """

        if max_skew < 0:
            raise ValueError("max_skew must be >= 0")
        normalized = mode.strip().lower()
        if normalized not in self._VALID_MODES:
            raise ValueError("mode must be 'advisory' or 'hard'")
        self._max_skew = int(max_skew)
        self._mode = normalized
        self._counts: dict[str, dict[str, int]] = {}

    @property
    def max_skew(self) -> int:
        """Configured maximum turn-count skew."""

        return self._max_skew

    @property
    def mode(self) -> str:
        """Enforcement mode (``advisory`` or ``hard``)."""

        return self._mode

    def recommend(self, session_id: str, eligible_bot_ids: list[str]) -> FairnessSnapshot:
        """Return fairness snapshot and recommended least-served bot.

        Args:
            session_id: Session identifier (non-empty).
            eligible_bot_ids: Non-empty list of bot ids that may take a turn.

        Returns:
            FairnessSnapshot with recommendation.

        Raises:
            ValueError: When ids are empty.
        """

        sid = self._require_id(session_id, "session_id")
        bots = [self._require_id(bot, "bot_id") for bot in eligible_bot_ids]
        if not bots:
            raise ValueError("eligible_bot_ids must be non-empty")
        return self._snapshot(sid, bots)

    def record(self, session_id: str, bot_id: str, eligible_bot_ids: list[str]) -> FairnessSnapshot:
        """Record that ``bot_id`` took a turn.

        In ``hard`` mode, raises if recording would exceed ``max_skew``.

        Args:
            session_id: Session identifier (non-empty).
            bot_id: Bot that took the turn (must be in eligible list).
            eligible_bot_ids: Eligible bots for skew calculation.

        Returns:
            FairnessSnapshot after recording.

        Raises:
            ValueError: When ids are empty or bot not eligible.
            RuntimeError: In hard mode when skew would be exceeded.
        """

        sid = self._require_id(session_id, "session_id")
        bot = self._require_id(bot_id, "bot_id")
        bots = [self._require_id(item, "bot_id") for item in eligible_bot_ids]
        if not bots:
            raise ValueError("eligible_bot_ids must be non-empty")
        if bot not in bots:
            raise ValueError("bot_id must be in eligible_bot_ids")
        snap = self._snapshot(sid, bots)
        if self._mode == "hard" and not self._would_allow(sid, bot, bots):
            raise RuntimeError(
                f"turn fairness skew exceeded for session {sid!r} bot {bot!r}: max_skew={self._max_skew}"
            )
        bucket = self._counts.setdefault(sid, {})
        bucket[bot] = bucket.get(bot, 0) + 1
        return self._snapshot(sid, bots)

    def reset(self, session_id: str) -> bool:
        """Clear turn counts for ``session_id``.

        Args:
            session_id: Session identifier (non-empty).

        Returns:
            True when counts existed; False on miss.
        """

        sid = self._require_id(session_id, "session_id")
        return self._counts.pop(sid, None) is not None

    def _would_allow(self, session_id: str, bot_id: str, eligible: list[str]) -> bool:
        """Allow bots whose current count is within max_skew of the minimum."""

        counts = {bot: self._counts.get(session_id, {}).get(bot, 0) for bot in eligible}
        minimum = min(counts.values()) if counts else 0
        return counts.get(bot_id, 0) <= minimum + self._max_skew

    def _snapshot(self, session_id: str, eligible: list[str]) -> FairnessSnapshot:
        counts = {bot: self._counts.get(session_id, {}).get(bot, 0) for bot in eligible}
        values = list(counts.values())
        skew = (max(values) - min(values)) if values else 0
        # Least served; tie-break lexicographic
        recommended = sorted(eligible, key=lambda bot: (counts[bot], bot))[0]
        allowed = True
        if self._mode == "hard":
            # Allow only bots that would not exceed skew
            allowed = any(self._would_allow(session_id, bot, eligible) for bot in eligible)
        return FairnessSnapshot(
            session_id=session_id,
            counts=counts,
            recommended_bot_id=recommended,
            max_skew=skew,
            mode=self._mode,
            allowed=allowed,
        )

    @staticmethod
    def _require_id(value: str, label: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError(f"{label} must be non-empty")
        return stripped
