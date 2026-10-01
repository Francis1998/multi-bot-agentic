"""Tool result cardinality gate.

Gates tool-result item counts with HITL bands. Distinct from
``ToolResultSchemaHashGate`` and ``ToolResultFingerprintDeduper``.
Fills a gap vs AutoGen / CrewAI / LangGraph tool-result
cardinality controls. Works with GPT-5.5 / Claude Sonnet 4.6 /
Gemini 3.x / Kimi K2. Never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolResultCardinalityStatus:
    """Tool result cardinality status."""

    session_id: str
    tool_name: str
    item_count: int
    soft_limit: int
    hard_limit: int
    band: str
    requires_human_review: bool


class ToolResultCardinalityGate:
    """Gate tool-result cardinality vs soft/hard limits."""

    def __init__(self, *, soft_limit: int = 100, hard_limit: int = 1000) -> None:
        """Initialize soft/hard item-count limits.

        Args:
            soft_limit: Soft max item count (``> 0``).
            hard_limit: Hard max item count (``> soft_limit``).
        """

        if soft_limit <= 0:
            raise ValueError("soft_limit must be > 0")
        if hard_limit <= soft_limit:
            raise ValueError("hard_limit must be > soft_limit")
        self._soft = soft_limit
        self._hard = hard_limit

    def check(
        self,
        session_id: str,
        *,
        tool_name: str,
        item_count: int,
    ) -> ToolResultCardinalityStatus:
        """Return cardinality band for one tool result.

        Args:
            session_id: Non-empty session id.
            tool_name: Non-empty tool name.
            item_count: Result item count (``>= 0``).

        Returns:
            ToolResultCardinalityStatus with ``requires_human_review=True``.
        """

        sid = session_id.strip()
        name = tool_name.strip()
        if not sid:
            raise ValueError("session_id must be non-empty")
        if not name:
            raise ValueError("tool_name must be non-empty")
        if item_count < 0:
            raise ValueError("item_count must be >= 0")

        if item_count <= self._soft:
            band = "ok"
        elif item_count <= self._hard:
            band = "elevated"
        else:
            band = "blocked"

        return ToolResultCardinalityStatus(
            session_id=sid,
            tool_name=name,
            item_count=int(item_count),
            soft_limit=self._soft,
            hard_limit=self._hard,
            band=band,
            requires_human_review=True,
        )
