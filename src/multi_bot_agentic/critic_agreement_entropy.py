"""Critic agreement entropy gate.

Flags Shannon entropy of critic verdict label distributions with HITL bands.
Distinct from ``CriticVerdictDiversityGate`` (verdict diversity) and
``CriticTimeoutBandGuard`` (timeout). Fills a gap vs AutoGen / CrewAI / LangGraph critic agreement-entropy gates.
Works with GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2.
Never performs network I/O.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class CriticAgreementEntropyStatus:
    """Critic agreement entropy status."""

    session_id: str
    verdict_count: int
    unique_labels: int
    entropy: float
    soft_limit: float
    hard_limit: float
    band: str
    requires_human_review: bool


class CriticAgreementEntropyGate:
    """Gate critic agreement entropy vs soft/hard limits."""

    def __init__(self, *, soft_limit: float = 1.0, hard_limit: float = 1.5) -> None:
        """Initialize entropy limits (nats).

        Args:
            soft_limit: Soft entropy threshold (``> 0``).
            hard_limit: Hard entropy threshold (``> soft_limit``).
        """

        if soft_limit <= 0:
            raise ValueError("soft_limit must be > 0")
        if hard_limit <= soft_limit:
            raise ValueError("hard_limit must be > soft_limit")
        self._soft = float(soft_limit)
        self._hard = float(hard_limit)

    def check(
        self,
        session_id: str,
        *,
        verdicts: Sequence[str],
    ) -> CriticAgreementEntropyStatus:
        """Return entropy band for critic verdict labels.

        Args:
            session_id: Non-empty session id.
            verdicts: Non-empty sequence of non-empty verdict labels.

        Returns:
            CriticAgreementEntropyStatus with ``requires_human_review=True``.
        """

        sid = session_id.strip()
        if not sid:
            raise ValueError("session_id must be non-empty")
        if not verdicts:
            raise ValueError("verdicts must be non-empty")
        labels = [v.strip() for v in verdicts]
        if any(not label for label in labels):
            raise ValueError("verdict labels must be non-empty")

        counts = Counter(labels)
        total = sum(counts.values())
        entropy = 0.0
        for count in counts.values():
            p = count / total
            entropy -= p * math.log(p)
        entropy = round(entropy, 4)

        if entropy >= self._hard:
            band = "hard"
        elif entropy >= self._soft:
            band = "soft"
        else:
            band = "ok"

        return CriticAgreementEntropyStatus(
            session_id=sid,
            verdict_count=int(total),
            unique_labels=len(counts),
            entropy=float(entropy),
            soft_limit=self._soft,
            hard_limit=self._hard,
            band=band,
            requires_human_review=True,
        )
