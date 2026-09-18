"""Fingerprint-based tool-result deduper for multi-bot sessions.

Hashes canonical tool results per ``session_id`` so identical payloads are
not re-injected into LLM context. Distinct from ``ToolCallIdempotencyCache``
(caches by tool+args before execute) and ``ToolResultTruncator`` (size trim).
Fills a gap vs AutoGen / CrewAI / LangGraph, which often re-emit duplicate
observations. Works with GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2.
Never performs network I/O.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DedupDecision:
    """Result of a tool-result dedupe check.

    Attributes:
        session_id: Conversation / session identifier.
        fingerprint: SHA-256 hex digest of the canonical payload.
        is_duplicate: True when fingerprint was already seen.
        seen_count: Times this fingerprint has been observed (including now).
        accepted: True when the payload should be forwarded to context.
    """

    session_id: str
    fingerprint: str
    is_duplicate: bool
    seen_count: int
    accepted: bool


class ToolResultFingerprintDeduper:
    """Drop duplicate tool-result payloads within a session.

    Caller-driven v1: ``observe`` after a tool returns. First sighting is
    accepted; later identical fingerprints are marked duplicate. Never
    performs network I/O.
    """

    def __init__(self, *, drop_duplicates: bool = True) -> None:
        """Create a fingerprint deduper.

        Args:
            drop_duplicates: When True, ``accepted`` is False for duplicates.
                When False, duplicates are still flagged but accepted.
        """

        self._drop_duplicates = bool(drop_duplicates)
        self._seen: dict[str, dict[str, int]] = {}

    @property
    def drop_duplicates(self) -> bool:
        """Whether duplicates are rejected from context."""

        return self._drop_duplicates

    def observe(self, session_id: str, payload: Any) -> DedupDecision:
        """Record a tool-result payload and return dedupe decision.

        Args:
            session_id: Session identifier (non-empty).
            payload: JSON-serializable tool result (str/dict/list/number/bool/None).

        Returns:
            DedupDecision for this observation.

        Raises:
            ValueError: When ``session_id`` is empty or payload is not
                JSON-serializable.
        """

        sid = session_id.strip()
        if not sid:
            raise ValueError("session_id must be non-empty")
        fingerprint = self._fingerprint(payload)
        bucket = self._seen.setdefault(sid, {})
        prior = bucket.get(fingerprint, 0)
        count = prior + 1
        bucket[fingerprint] = count
        is_dup = prior > 0
        accepted = True
        if is_dup and self._drop_duplicates:
            accepted = False
        return DedupDecision(
            session_id=sid,
            fingerprint=fingerprint,
            is_duplicate=is_dup,
            seen_count=count,
            accepted=accepted,
        )

    def reset(self, session_id: str) -> bool:
        """Clear fingerprints for ``session_id``.

        Args:
            session_id: Session identifier (non-empty).

        Returns:
            True when fingerprints existed; False on miss.
        """

        sid = session_id.strip()
        if not sid:
            raise ValueError("session_id must be non-empty")
        return self._seen.pop(sid, None) is not None

    @staticmethod
    def _fingerprint(payload: Any) -> str:
        try:
            canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        except (TypeError, ValueError) as exc:
            raise ValueError("payload must be JSON-serializable") from exc
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
