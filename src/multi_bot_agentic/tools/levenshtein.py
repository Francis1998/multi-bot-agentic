"""Levenshtein edit-distance tool for agent pipelines.

CrewAI / LangGraph-style agents often need a deterministic similarity signal
when fuzzy-matching labels, ticket ids, or user typos. Asking a model to
compute edit distance is unreliable. This tool returns the classic
Levenshtein distance (insert/delete/substitute cost 1) between two strings
via a bounded DP table. It never executes code and never makes network
requests. Safe for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.
"""

from __future__ import annotations

from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_CHARS: Final[int] = 2_000


class LevenshteinTool:
    """Compute Levenshtein edit distance between two strings."""

    name = "levenshtein"
    description = "Returns Levenshtein edit distance between arguments a and b (max 2000 chars each); no network."

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Return the edit distance between ``a`` and ``b``.

        Args:
            invocation: Tool invocation with required ``a`` and ``b`` strings.

        Returns:
            Tool result whose ``content`` is the decimal distance, or
            ``ok=False`` on validation failure.
        """

        raw_a = invocation.arguments.get("a")
        raw_b = invocation.arguments.get("b")
        if raw_a is None or raw_b is None:
            return self._fail("missing required arguments: a and b", {})
        a = str(raw_a)
        b = str(raw_b)
        if len(a) > _MAX_CHARS or len(b) > _MAX_CHARS:
            return self._fail(
                f"input exceeds max {_MAX_CHARS} chars",
                {"a_chars": len(a), "b_chars": len(b)},
            )

        distance = self._distance(a, b)
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=str(distance),
            metadata={
                "distance": distance,
                "a_chars": len(a),
                "b_chars": len(b),
            },
        )

    @staticmethod
    def _distance(left: str, right: str) -> int:
        """Compute classic Levenshtein distance with unit costs."""

        if left == right:
            return 0
        if not left:
            return len(right)
        if not right:
            return len(left)
        # Ensure right is the shorter row for memory.
        if len(left) < len(right):
            left, right = right, left
        previous = list(range(len(right) + 1))
        for i, left_ch in enumerate(left, start=1):
            current = [i]
            for j, right_ch in enumerate(right, start=1):
                insert_cost = current[j - 1] + 1
                delete_cost = previous[j] + 1
                replace_cost = previous[j - 1] + (0 if left_ch == right_ch else 1)
                current.append(min(insert_cost, delete_cost, replace_cost))
            previous = current
        return previous[-1]

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
