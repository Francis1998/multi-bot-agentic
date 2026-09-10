"""Speculative tool prefetch planner for multi-bot ODA loops.

Warm likely next tools without executing them — returns an ordered prefetch
plan the runner can use to prime caches / load adapters. Distinct from
LangGraph parallel nodes and CrewAI async tool fan-out: this never invokes
tools. Suitable for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 loops.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PrefetchPlan:
    """Ordered speculative prefetch plan.

    Attributes:
        tool_names: Tools to warm, highest priority first.
        reason: Human-readable explanation of ranking.
    """

    tool_names: list[str]
    reason: str


class SpeculativeToolPrefetch:
    """Rank likely next tools from recent history without executing them."""

    def __init__(self, *, max_prefetch: int = 3) -> None:
        if max_prefetch < 1:
            raise ValueError("max_prefetch must be >= 1")
        self._max_prefetch = max_prefetch

    @property
    def max_prefetch(self) -> int:
        """Return configured max_prefetch."""

        return self._max_prefetch

    def plan(
        self,
        *,
        recent_tools: list[str],
        available_tools: list[str],
        hint: str | None = None,
    ) -> PrefetchPlan:
        """Build a speculative prefetch plan.

        Args:
            recent_tools: Recently used tool names (oldest → newest).
            available_tools: Tools that may be warmed.
            hint: Optional free-text hint; matching tool names are boosted.

        Returns:
            PrefetchPlan with up to ``max_prefetch`` tool names (never executes).

        Raises:
            TypeError: When recent_tools or available_tools is not a list.
        """

        if not isinstance(recent_tools, list):
            raise TypeError("recent_tools must be a list")
        if not isinstance(available_tools, list):
            raise TypeError("available_tools must be a list")

        available = []
        seen_avail: set[str] = set()
        for name in available_tools:
            cleaned = str(name).strip()
            if cleaned and cleaned not in seen_avail:
                available.append(cleaned)
                seen_avail.add(cleaned)

        if not available:
            return PrefetchPlan(tool_names=[], reason="no available tools")

        scores: dict[str, float] = dict.fromkeys(available, 0.0)
        for index, raw in enumerate(recent_tools):
            name = str(raw).strip()
            if name not in scores:
                continue
            # Newer uses score higher.
            scores[name] += 1.0 + (index / max(len(recent_tools), 1))

        hint_text = (hint or "").strip().lower()
        if hint_text:
            for name in available:
                if name.lower() in hint_text or any(token and token in name.lower() for token in hint_text.split()):
                    scores[name] += 5.0

        ranked = sorted(available, key=lambda n: (-scores[n], n))
        selected = ranked[: self._max_prefetch]
        if hint_text and any(scores[n] >= 5.0 for n in selected):
            reason = "hint boost + recent-tool recency"
        elif any(scores[n] > 0 for n in selected):
            reason = "recent-tool recency"
        else:
            reason = "stable alphabetical fallback"

        return PrefetchPlan(tool_names=selected, reason=reason)
