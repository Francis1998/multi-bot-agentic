"""Critic-verdict diversity gate.

Flags low diversity when critic bots emit near-identical verdict strings.
Distinct from ``CriticPassBudgetLimiter`` (pass count) and
``CriticBotVerdictGate`` (single verdict). Fills a gap vs AutoGen /
CrewAI / LangGraph echo-chamber critic loops. Works with GPT-5.5 /
Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. Never performs network I/O.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class CriticVerdictDiversityStatus:
    """Critic verdict diversity status."""

    session_id: str
    unique_verdicts: int
    total_verdicts: int
    diversity_ratio: float
    band: str
    requires_human_review: bool


class CriticVerdictDiversityGate:
    """Gate low-diversity critic verdict sets."""

    def check(
        self,
        session_id: str,
        verdicts: Sequence[str],
        *,
        min_diversity_ratio: float = 0.5,
    ) -> CriticVerdictDiversityStatus:
        """Return diversity status for critic verdicts.

        Args:
            session_id: Non-empty session id.
            verdicts: Critic verdict strings (casefolded for uniqueness).
            min_diversity_ratio: Ratio below which band is ``echo_chamber``.

        Returns:
            CriticVerdictDiversityStatus with ``requires_human_review=True``.
        """

        sid = session_id.strip()
        if not sid:
            raise ValueError("session_id must be non-empty")
        if min_diversity_ratio <= 0 or min_diversity_ratio > 1:
            raise ValueError("min_diversity_ratio must be in (0, 1]")

        cleaned = [v.strip().casefold() for v in verdicts if v and v.strip()]
        total = len(cleaned)
        unique = len(set(cleaned))
        ratio = 1.0 if total == 0 else round(unique / total, 4)

        if total == 0:
            band = "empty"
        elif ratio < min_diversity_ratio:
            band = "echo_chamber"
        elif ratio < 0.85:
            band = "low_diversity"
        else:
            band = "diverse"

        return CriticVerdictDiversityStatus(
            session_id=sid,
            unique_verdicts=int(unique),
            total_verdicts=int(total),
            diversity_ratio=float(ratio),
            band=band,
            requires_human_review=True,
        )
