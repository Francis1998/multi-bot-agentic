"""HITL escalation cooldown gate after human deny/reject.

Tracks wall-clock cooldown after a human denies or rejects an escalation so
bots cannot immediately re-prompt the same HITL surface. Distinct from
``HitlApprovalGate`` (approve/deny decision) and ``CriticBotVerdictGate``
(critic accept/revise/reject). Fills a gap vs AutoGen / CrewAI / LangGraph
HITL nodes that often allow immediate re-escalation. Works with GPT-5.5 /
Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. Never performs network I/O.
"""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass(frozen=True)
class CooldownStatus:
    """Snapshot of HITL escalation cooldown for a key.

    Attributes:
        key: Escalation key (session + action or similar).
        cooling_down: True while within the cooldown window.
        remaining_seconds: Seconds left in cooldown (0 when clear).
        deny_count: Times ``record_deny`` has been called for this key.
        mode: ``advisory`` or ``hard``.
        allowed: True when a new escalation is permitted under the mode.
    """

    key: str
    cooling_down: bool
    remaining_seconds: float
    deny_count: int
    mode: str
    allowed: bool


class HitlEscalationCooldownGate:
    """Gate re-escalation attempts after a human deny.

    Caller-driven v1: ``record_deny`` after HITL reject, ``check`` before a
    new escalation. Never performs network I/O.
    """

    _VALID_MODES = frozenset({"advisory", "hard"})

    def __init__(self, *, cooldown_seconds: float, mode: str = "advisory") -> None:
        """Create an escalation cooldown gate.

        Args:
            cooldown_seconds: Positive cooldown window in seconds.
            mode: ``advisory`` (status only; always allows) or ``hard``
                (denies while cooling down).

        Raises:
            ValueError: When cooldown is not positive or mode is invalid.
        """

        if cooldown_seconds <= 0:
            raise ValueError("cooldown_seconds must be > 0")
        normalized = mode.strip().lower()
        if normalized not in self._VALID_MODES:
            raise ValueError("mode must be 'advisory' or 'hard'")
        self._cooldown_seconds = float(cooldown_seconds)
        self._mode = normalized
        self._denies: dict[str, tuple[float, int]] = {}

    @property
    def cooldown_seconds(self) -> float:
        """Configured cooldown window in seconds."""

        return self._cooldown_seconds

    @property
    def mode(self) -> str:
        """Enforcement mode (``advisory`` or ``hard``)."""

        return self._mode

    def record_deny(self, key: str, *, now: float | None = None) -> CooldownStatus:
        """Record a human deny and start/refresh the cooldown window.

        Args:
            key: Escalation key (non-empty).
            now: Optional monotonic/unix timestamp override for tests.

        Returns:
            CooldownStatus after recording.

        Raises:
            ValueError: When ``key`` is empty.
        """

        cleaned = key.strip()
        if not cleaned:
            raise ValueError("key must be non-empty")
        stamp = time.monotonic() if now is None else float(now)
        prior = self._denies.get(cleaned, (0.0, 0))
        self._denies[cleaned] = (stamp, prior[1] + 1)
        return self._status(cleaned, stamp)

    def check(self, key: str, *, now: float | None = None) -> CooldownStatus:
        """Return cooldown status without mutating state.

        Args:
            key: Escalation key (non-empty).
            now: Optional timestamp override for tests.

        Returns:
            CooldownStatus for the key.

        Raises:
            ValueError: When ``key`` is empty.
        """

        cleaned = key.strip()
        if not cleaned:
            raise ValueError("key must be non-empty")
        stamp = time.monotonic() if now is None else float(now)
        return self._status(cleaned, stamp)

    def reset(self, key: str) -> bool:
        """Clear cooldown state for ``key``.

        Args:
            key: Escalation key (non-empty).

        Returns:
            True when state existed; False on miss.
        """

        cleaned = key.strip()
        if not cleaned:
            raise ValueError("key must be non-empty")
        return self._denies.pop(cleaned, None) is not None

    def _status(self, key: str, now: float) -> CooldownStatus:
        entry = self._denies.get(key)
        if entry is None:
            return CooldownStatus(
                key=key,
                cooling_down=False,
                remaining_seconds=0.0,
                deny_count=0,
                mode=self._mode,
                allowed=True,
            )
        last, count = entry
        elapsed = max(0.0, now - last)
        remaining = max(0.0, self._cooldown_seconds - elapsed)
        cooling = remaining > 0.0
        allowed = True if self._mode == "advisory" else not cooling
        return CooldownStatus(
            key=key,
            cooling_down=cooling,
            remaining_seconds=round(remaining, 3),
            deny_count=count,
            mode=self._mode,
            allowed=allowed,
        )
