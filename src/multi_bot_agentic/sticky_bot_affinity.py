"""Sticky session→bot affinity store for multi-bot continuity.

Pins a ``session_id`` to a ``bot_id`` so subsequent turns stay on the same
bot without re-routing. Distinct from ``BotHandoffReceiptStore`` (audit
receipts for handoffs) — this is a thin, stdlib-only affinity map for
GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 multi-bot loops. Fills a
gap vs AutoGen/CrewAI/LangGraph, which often reselect agents each turn
without sticky session pins.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class StickyBotBinding:
    """Immutable session→bot affinity pin.

    Attributes:
        session_id: Conversation / session identifier.
        bot_id: Bot pinned for this session.
        bound_at_iso: UTC ISO-8601 timestamp when the pin was set.
    """

    session_id: str
    bot_id: str
    bound_at_iso: str


class StickyBotAffinityStore:
    """In-memory sticky bot affinity for multi-bot sessions.

    Caller-driven v1: ``set`` after choosing a bot; ``get`` on subsequent
    turns; ``clear`` when the session ends or affinity should reset. Never
    performs network I/O.
    """

    def __init__(self) -> None:
        self._bindings: dict[str, StickyBotBinding] = {}

    def set(
        self,
        session_id: str,
        bot_id: str,
        *,
        bound_at_iso: str | None = None,
    ) -> StickyBotBinding:
        """Pin ``session_id`` to ``bot_id`` (overwrites any prior pin).

        Args:
            session_id: Session identifier (non-empty).
            bot_id: Bot identifier (non-empty).
            bound_at_iso: Optional UTC ISO timestamp; defaults to now.

        Returns:
            Newly stored StickyBotBinding.

        Raises:
            ValueError: When ``session_id`` or ``bot_id`` is empty.
        """

        if not session_id.strip():
            raise ValueError("session_id must be non-empty")
        if not bot_id.strip():
            raise ValueError("bot_id must be non-empty")

        sid = session_id.strip()
        binding = StickyBotBinding(
            session_id=sid,
            bot_id=bot_id.strip(),
            bound_at_iso=bound_at_iso or datetime.now(timezone.utc).isoformat(),
        )
        self._bindings[sid] = binding
        return binding

    def get(self, session_id: str) -> StickyBotBinding | None:
        """Return the binding for ``session_id``, or None if unset.

        Args:
            session_id: Session identifier (non-empty).

        Returns:
            StickyBotBinding or None.

        Raises:
            ValueError: When ``session_id`` is empty.
        """

        if not session_id.strip():
            raise ValueError("session_id must be non-empty")
        return self._bindings.get(session_id.strip())

    def clear(self, session_id: str) -> bool:
        """Remove the binding for ``session_id`` if present.

        Args:
            session_id: Session identifier (non-empty).

        Returns:
            True when a binding was removed; False on miss.

        Raises:
            ValueError: When ``session_id`` is empty.
        """

        if not session_id.strip():
            raise ValueError("session_id must be non-empty")
        return self._bindings.pop(session_id.strip(), None) is not None
