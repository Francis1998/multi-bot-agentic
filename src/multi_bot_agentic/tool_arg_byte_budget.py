"""Tool-argument byte budget guard.

Caps serialized tool-argument payload size and emits HITL bands.
Distinct from ``ToolResultTruncator`` (result strings) and
``ToolArgumentSanitizer`` (secret scrub). Fills a gap vs AutoGen /
CrewAI / LangGraph unbounded tool-arg payloads. Works with GPT-5.5 /
Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. Never performs network I/O.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolArgByteBudgetStatus:
    """Tool-argument byte budget status."""

    tool_name: str
    arg_bytes: int
    max_bytes: int
    remaining: int
    band: str
    requires_human_review: bool


class ToolArgByteBudgetGuard:
    """Guard serialized tool-argument byte budgets."""

    def check(
        self,
        tool_name: str,
        arguments: Mapping[str, Any],
        *,
        max_bytes: int = 8192,
    ) -> ToolArgByteBudgetStatus:
        """Return byte-budget status for one tool call.

        Args:
            tool_name: Non-empty tool name.
            arguments: Tool arguments mapping.
            max_bytes: Hard byte cap (``>= 1``).

        Returns:
            ToolArgByteBudgetStatus with ``requires_human_review=True``.
        """

        name = tool_name.strip()
        if not name:
            raise ValueError("tool_name must be non-empty")
        if max_bytes < 1:
            raise ValueError("max_bytes must be >= 1")

        payload = json.dumps(dict(arguments), sort_keys=True, default=str)
        arg_bytes = len(payload.encode("utf-8"))
        remaining = max(0, max_bytes - arg_bytes)
        if remaining == 0 or arg_bytes > max_bytes:
            band = "exhausted"
            remaining = 0
        elif remaining <= max(1, max_bytes // 10):
            band = "near_limit"
        else:
            band = "ok"

        return ToolArgByteBudgetStatus(
            tool_name=name,
            arg_bytes=int(arg_bytes),
            max_bytes=int(max_bytes),
            remaining=int(remaining),
            band=band,
            requires_human_review=True,
        )
