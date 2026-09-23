"""Tool output schema gate for multi-bot tool results.

Validates required keys on tool outputs for HITL review. Distinct from
``schema_validate`` (JSON schema helpers) and ``ArgumentSanitizer`` (inputs).
Fills a gap vs AutoGen / CrewAI / LangGraph tool-result schema checks.
Works with GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2.
Never performs network I/O.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class ToolOutputSchemaVerdict:
    """Schema gate verdict for one tool output.

    Attributes:
        tool_name: Tool identifier.
        missing_keys: Required keys absent from output.
        band: ``pass`` / ``fail``.
        requires_human_review: Always True for HITL.
    """

    tool_name: str
    missing_keys: tuple[str, ...]
    band: str
    requires_human_review: bool


class ToolOutputSchemaGate:
    """Gate tool outputs against required key names."""

    def check(
        self,
        tool_name: str,
        output: Mapping[str, object],
        *,
        required_keys: Sequence[str],
    ) -> ToolOutputSchemaVerdict:
        """Return pass/fail for required keys.

        Args:
            tool_name: Non-empty tool name.
            output: Tool output mapping.
            required_keys: Required key names (non-empty).

        Returns:
            ToolOutputSchemaVerdict with ``requires_human_review=True``.
        """

        name = tool_name.strip()
        if not name:
            raise ValueError("tool_name must be non-empty")
        keys = tuple(k.strip() for k in required_keys if k.strip())
        if not keys:
            raise ValueError("required_keys must be non-empty")

        missing = tuple(k for k in keys if k not in output)
        band = "fail" if missing else "pass"
        return ToolOutputSchemaVerdict(
            tool_name=name,
            missing_keys=missing,
            band=band,
            requires_human_review=True,
        )
