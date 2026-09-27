"""Shared-memory conflict band guard.

Flags concurrent write conflicts on shared memory keys using a simple
version-skew heuristic and emits HITL bands. Distinct from
``SharedMemoryQuotaGuard`` (byte quotas) and
``SharedBlackboardWriteLease`` (lease locking). Fills a gap vs AutoGen /
CrewAI / LangGraph CRDT-style conflict surfacing. Works with GPT-5.5 /
Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. Never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SharedMemoryConflictStatus:
    """Shared memory conflict status."""

    session_id: str
    key: str
    local_version: int
    remote_version: int
    version_skew: int
    band: str
    requires_human_review: bool


class SharedMemoryConflictBandGuard:
    """Surface shared-memory version-skew conflict bands."""

    def check(
        self,
        session_id: str,
        *,
        key: str,
        local_version: int,
        remote_version: int,
        warn_skew: int = 1,
        conflict_skew: int = 3,
    ) -> SharedMemoryConflictStatus:
        """Return conflict band from version skew.

        Args:
            session_id: Non-empty session id.
            key: Non-empty memory key.
            local_version: Local key version (``>= 0``).
            remote_version: Remote key version (``>= 0``).
            warn_skew: Warn at this absolute skew (``> 0``).
            conflict_skew: Conflict at this absolute skew (``>= warn_skew``).

        Returns:
            SharedMemoryConflictStatus with ``requires_human_review=True``.
        """

        sid = session_id.strip()
        mem_key = key.strip()
        if not sid:
            raise ValueError("session_id must be non-empty")
        if not mem_key:
            raise ValueError("key must be non-empty")
        if local_version < 0 or remote_version < 0:
            raise ValueError("versions must be >= 0")
        if warn_skew <= 0:
            raise ValueError("warn_skew must be > 0")
        if conflict_skew < warn_skew:
            raise ValueError("conflict_skew must be >= warn_skew")

        skew = abs(int(local_version) - int(remote_version))
        if skew >= conflict_skew:
            band = "conflict"
        elif skew >= warn_skew:
            band = "diverge"
        else:
            band = "aligned"

        return SharedMemoryConflictStatus(
            session_id=sid,
            key=mem_key,
            local_version=int(local_version),
            remote_version=int(remote_version),
            version_skew=int(skew),
            band=band,
            requires_human_review=True,
        )
