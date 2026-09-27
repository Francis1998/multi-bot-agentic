"""Tool-result PII redaction gate.

Scans tool-result text for high-risk PII patterns and emits HITL bands
before results re-enter the conversation. Distinct from
``ObservationRedactor`` (observation stream) and ``RedactionTool``
(explicit tool). Fills a gap vs AutoGen / CrewAI / LangGraph tool-result
PII gates. Works with GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2.
Never performs network I/O.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_PHONE = re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")


@dataclass(frozen=True)
class ToolResultPiiStatus:
    """Tool-result PII gate status."""

    tool_name: str
    match_count: int
    matched_kinds: tuple[str, ...]
    band: str
    requires_human_review: bool


class ToolResultPiiRedactionGate:
    """Gate tool results that appear to contain PII."""

    def check(self, tool_name: str, *, result_text: str) -> ToolResultPiiStatus:
        """Return PII risk band for a tool result.

        Args:
            tool_name: Non-empty tool name.
            result_text: Tool result text to scan (may be empty).

        Returns:
            ToolResultPiiStatus with ``requires_human_review=True``.
        """

        name = tool_name.strip()
        if not name:
            raise ValueError("tool_name must be non-empty")

        kinds: list[str] = []
        text = result_text or ""
        if _EMAIL.search(text):
            kinds.append("email")
        if _SSN.search(text):
            kinds.append("ssn")
        if _PHONE.search(text):
            kinds.append("phone")

        count = len(kinds)
        if count >= 2 or "ssn" in kinds:
            band = "block"
        elif count == 1:
            band = "redact"
        else:
            band = "clear"

        return ToolResultPiiStatus(
            tool_name=name,
            match_count=int(count),
            matched_kinds=tuple(kinds),
            band=band,
            requires_human_review=True,
        )
