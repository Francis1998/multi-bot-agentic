"""Exclusive bot-role conflict detector for multi-bot sessions.

Detects when two or more bots claim the same exclusive role tag within a
session (e.g. two ``critic`` bots). Distinct from ``BotSkillTagRouter``
(skill overlap ranking) and ``BotTurnFairnessScheduler`` (turn counts).
Fills a gap vs AutoGen / CrewAI / LangGraph, which often allow silent
role collisions. Works with GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x /
Kimi K2. Never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RoleConflictReport:
    """Result of an exclusive-role conflict scan.

    Attributes:
        session_id: Conversation / session identifier.
        role: Exclusive role tag inspected.
        claimants: Bot ids claiming the role.
        conflict: True when more than one claimant is present.
        allowed: True when the claim set is conflict-free under mode.
        mode: ``advisory`` or ``hard``.
    """

    session_id: str
    role: str
    claimants: tuple[str, ...]
    conflict: bool
    allowed: bool
    mode: str


class BotRoleConflictDetector:
    """Track exclusive role claims and flag multi-claimant conflicts."""

    def __init__(self, *, mode: str = "advisory") -> None:
        """Create a role-conflict detector.

        Args:
            mode: ``advisory`` keeps ``allowed=True`` on conflict;
                ``hard`` sets ``allowed=False``.

        Raises:
            ValueError: When mode is not advisory/hard.
        """

        if mode not in {"advisory", "hard"}:
            raise ValueError("mode must be 'advisory' or 'hard'")
        self._mode = mode
        self._claims: dict[str, dict[str, set[str]]] = {}

    @property
    def mode(self) -> str:
        """Return configured enforcement mode."""

        return self._mode

    def claim(self, session_id: str, bot_id: str, role: str) -> RoleConflictReport:
        """Record a bot claiming an exclusive role and return conflict status.

        Args:
            session_id: Non-empty session id.
            bot_id: Non-empty bot id.
            role: Non-empty exclusive role tag.

        Returns:
            RoleConflictReport for this claim.

        Raises:
            ValueError: On empty identifiers.
        """

        sid = session_id.strip()
        bid = bot_id.strip()
        role_key = role.strip().lower()
        if not sid:
            raise ValueError("session_id must be non-empty")
        if not bid:
            raise ValueError("bot_id must be non-empty")
        if not role_key:
            raise ValueError("role must be non-empty")
        bucket = self._claims.setdefault(sid, {})
        holders = bucket.setdefault(role_key, set())
        holders.add(bid)
        claimants = tuple(sorted(holders))
        conflict = len(claimants) > 1
        allowed = True
        if conflict and self._mode == "hard":
            allowed = False
        return RoleConflictReport(
            session_id=sid,
            role=role_key,
            claimants=claimants,
            conflict=conflict,
            allowed=allowed,
            mode=self._mode,
        )

    def release(self, session_id: str, bot_id: str, role: str) -> bool:
        """Release a bot's claim on ``role``.

        Returns:
            True when a claim existed.
        """

        sid = session_id.strip()
        bid = bot_id.strip()
        role_key = role.strip().lower()
        if not sid or not bid or not role_key:
            raise ValueError("session_id, bot_id, and role must be non-empty")
        holders = self._claims.get(sid, {}).get(role_key)
        if not holders or bid not in holders:
            return False
        holders.remove(bid)
        if not holders:
            del self._claims[sid][role_key]
        return True

    def reset(self, session_id: str) -> bool:
        """Clear all role claims for ``session_id``."""

        sid = session_id.strip()
        if not sid:
            raise ValueError("session_id must be non-empty")
        return self._claims.pop(sid, None) is not None
