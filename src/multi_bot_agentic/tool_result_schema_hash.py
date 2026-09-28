"""Tool-result schema hash gate.

Compares an expected schema hash to the observed tool-result schema hash
and emits HITL bands on drift. Distinct from ``ToolOutputSchemaGate``
(required keys) and ``ToolResultPiiRedactionGate`` (PII). Fills a gap vs
AutoGen / CrewAI / LangGraph tool-result schema drift. Works with GPT-5.5 /
Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. Never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolResultSchemaHashStatus:
    """Tool-result schema hash gate status."""

    tool_name: str
    expected_hash: str
    observed_hash: str
    band: str
    requires_human_review: bool


class ToolResultSchemaHashGate:
    """Gate tool results whose schema hash drifts from expected."""

    def check(
        self,
        tool_name: str,
        *,
        expected_hash: str,
        observed_hash: str,
    ) -> ToolResultSchemaHashStatus:
        """Return schema-hash drift band for a tool result.

        Args:
            tool_name: Non-empty tool name.
            expected_hash: Non-empty expected schema hash.
            observed_hash: Non-empty observed schema hash.

        Returns:
            ToolResultSchemaHashStatus with ``requires_human_review=True``.
        """

        name = tool_name.strip()
        expected = expected_hash.strip()
        observed = observed_hash.strip()
        if not name:
            raise ValueError("tool_name must be non-empty")
        if not expected:
            raise ValueError("expected_hash must be non-empty")
        if not observed:
            raise ValueError("observed_hash must be non-empty")

        if expected == observed:
            band = "match"
        elif expected[:8] == observed[:8]:
            band = "near_match"
        else:
            band = "drift"

        return ToolResultSchemaHashStatus(
            tool_name=name,
            expected_hash=expected,
            observed_hash=observed,
            band=band,
            requires_human_review=True,
        )
