"""Jaro-Winkler string similarity tool for agent pipelines.

CrewAI / LangGraph-style agents often need a fuzzy similarity signal when
matching labels or typos. Levenshtein gives edit distance; this companion
returns the classic Jaro-Winkler similarity in ``[0, 1]``. It never executes
code and never makes network requests. Safe for GPT-5.5 / Claude Sonnet 4.6 /
Gemini 3.x / Kimi K2 workers.
"""

from __future__ import annotations

from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_CHARS: Final[int] = 2_000
_PREFIX_SCALE: Final[float] = 0.1
_MAX_PREFIX: Final[int] = 4


class JaroWinklerTool:
    """Compute Jaro-Winkler similarity between two strings."""

    name = "jaro_winkler"
    description = (
        "Returns Jaro-Winkler similarity score 0..1 between arguments a and b (max 2000 chars each); no network."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Return the Jaro-Winkler similarity between ``a`` and ``b``.

        Args:
            invocation: Tool invocation with required ``a`` and ``b`` strings.

        Returns:
            Tool result whose ``content`` is the decimal similarity, or
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

        score = _jaro_winkler(a, b)
        if score == 0.0:
            content = "0"
        elif score == 1.0:
            content = "1"
        else:
            content = f"{score:.6f}".rstrip("0").rstrip(".")
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=content,
            metadata={
                "similarity": score,
                "a_chars": len(a),
                "b_chars": len(b),
            },
        )

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)


def _jaro_winkler(left: str, right: str) -> float:
    """Return Jaro-Winkler similarity in ``[0, 1]``."""

    jaro = _jaro(left, right)
    if jaro == 0.0:
        return 0.0
    prefix = 0
    limit = min(_MAX_PREFIX, len(left), len(right))
    while prefix < limit and left[prefix] == right[prefix]:
        prefix += 1
    return jaro + prefix * _PREFIX_SCALE * (1.0 - jaro)


def _jaro(left: str, right: str) -> float:
    """Return classic Jaro similarity in ``[0, 1]``."""

    if left == right:
        return 1.0
    len_l = len(left)
    len_r = len(right)
    if len_l == 0 or len_r == 0:
        return 0.0

    match_distance = max(len_l, len_r) // 2 - 1
    if match_distance < 0:
        match_distance = 0

    left_matches = [False] * len_l
    right_matches = [False] * len_r
    matches = 0
    transpositions = 0

    for i, ch in enumerate(left):
        start = max(0, i - match_distance)
        end = min(i + match_distance + 1, len_r)
        for j in range(start, end):
            if right_matches[j]:
                continue
            if ch != right[j]:
                continue
            left_matches[i] = True
            right_matches[j] = True
            matches += 1
            break

    if matches == 0:
        return 0.0

    k = 0
    for i in range(len_l):
        if not left_matches[i]:
            continue
        while not right_matches[k]:
            k += 1
        if left[i] != right[k]:
            transpositions += 1
        k += 1

    return (matches / len_l + matches / len_r + (matches - transpositions / 2.0) / matches) / 3.0
