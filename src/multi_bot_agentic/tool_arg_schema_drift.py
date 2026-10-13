"""ToolArgSchemaDriftGuard band guard.

Flags schema_drift_score pressure with HITL bands. Distinct from
`SchemaValidate` / `ToolResultSizeBombGuard`.
Fills a gap vs AutoGen/CrewAI/LangGraph tool-argument schema-drift guards.
Works with frontier multi-LLM stacks. Never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolArgSchemaDriftStatus:
    """ToolArgSchemaDriftGuard status."""

    session_id: str
    schema_drift_score: float
    soft_limit: float
    hard_limit: float
    band: str
    requires_human_review: bool


class ToolArgSchemaDriftGuard:
    """Gate schema_drift_score vs soft/hard limits."""

    def __init__(self, *, soft_limit: float = 0.15, hard_limit: float = 0.4) -> None:
        """Initialize limits.

        Args:
            soft_limit: Soft max (> 0).
            hard_limit: Hard max (> soft_limit).
        """

        if soft_limit <= 0:
            raise ValueError("soft_limit must be > 0")
        if hard_limit <= soft_limit:
            raise ValueError("hard_limit must be > soft_limit")
        self._soft = soft_limit
        self._hard = hard_limit

    def check(self, session_id: str, *, schema_drift_score: float) -> ToolArgSchemaDriftStatus:
        """Return band for observed schema_drift_score.

        Args:
            session_id: Non-empty id.
            schema_drift_score: Observed value (>= 0).

        Returns:
            ToolArgSchemaDriftStatus with ``requires_human_review=True``.
        """

        sid = session_id.strip()
        if not sid:
            raise ValueError("session_id must be non-empty")
        if schema_drift_score < 0:
            raise ValueError("schema_drift_score must be >= 0")

        if schema_drift_score <= self._soft:
            band = "ok"
        elif schema_drift_score <= self._hard:
            band = "elevated"
        else:
            band = "blocked"

        return ToolArgSchemaDriftStatus(
            session_id=sid,
            schema_drift_score=float(schema_drift_score),
            soft_limit=self._soft,
            hard_limit=self._hard,
            band=band,
            requires_human_review=True,
        )
