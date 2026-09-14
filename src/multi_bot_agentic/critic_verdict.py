"""Critic-bot verdict gate for accept / revise / reject on agent outputs.

Implements a thin critic pattern: a producer bot submits output, a critic
returns ``accept``, ``revise``, or ``reject`` with optional critique text.
Distinct from ``HitlApprovalGate`` (human file-backed tool approvals) —
this is an in-memory critic verdict store for GPT-5.5 / Claude Sonnet 4.6 /
Gemini 3.x / Kimi K2 multi-bot crews. Fills a gap vs AutoGen/CrewAI/LangGraph,
which often lack a first-class accept/revise/reject gate separate from the
producer agent loop.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from uuid import uuid4


class CriticVerdict(str, Enum):
    """Critic decision on a submitted agent output.

    Note:
        Exposed as ``(str, Enum)`` so Python 3.10 CI stays green (``StrEnum`` is 3.11+).
    """

    ACCEPT = "accept"
    REVISE = "revise"
    REJECT = "reject"


@dataclass(frozen=True)
class CriticReview:
    """One critic review of a producer bot's output.

    Attributes:
        review_id: Stable review identifier.
        bot_id: Producer bot that submitted the output.
        output_text: Output text under review.
        verdict: Critic decision, or None while pending.
        critique: Free-text critique from the critic bot.
        revision_hint: Optional hint when verdict is ``revise``.
    """

    review_id: str
    bot_id: str
    output_text: str
    verdict: CriticVerdict | None
    critique: str
    revision_hint: str

    @property
    def pending(self) -> bool:
        """True when no verdict has been recorded yet."""

        return self.verdict is None


class CriticBotVerdictGate:
    """In-memory accept/revise/reject gate for agent outputs.

    Caller-driven v1: ``submit`` after a producer turn, ``decide`` when the
    critic responds, ``get`` / ``list_pending`` for orchestration. Never
    performs network I/O.
    """

    def __init__(self) -> None:
        self._reviews: dict[str, CriticReview] = {}

    def submit(self, *, bot_id: str, output_text: str) -> CriticReview:
        """Create a pending critic review for ``output_text``.

        Args:
            bot_id: Producer bot identifier (non-empty).
            output_text: Output to review (non-empty after strip).

        Returns:
            Newly created pending CriticReview.

        Raises:
            ValueError: When ``bot_id`` or ``output_text`` is empty.
        """

        bid = self._require_nonempty(bot_id, "bot_id")
        text = self._require_nonempty(output_text, "output_text")
        review = CriticReview(
            review_id=str(uuid4()),
            bot_id=bid,
            output_text=text,
            verdict=None,
            critique="",
            revision_hint="",
        )
        self._reviews[review.review_id] = review
        return review

    def decide(
        self,
        review_id: str,
        *,
        verdict: CriticVerdict,
        critique: str = "",
        revision_hint: str = "",
    ) -> CriticReview:
        """Apply a critic verdict to a pending review.

        Args:
            review_id: Existing review identifier.
            verdict: ``accept``, ``revise``, or ``reject``.
            critique: Optional critique text.
            revision_hint: Required non-empty when verdict is ``revise``.

        Returns:
            Updated CriticReview.

        Raises:
            ValueError: Unknown/resolved review, or missing revision_hint.
            KeyError: When ``review_id`` is not found.
        """

        rid = self._require_nonempty(review_id, "review_id")
        if rid not in self._reviews:
            raise KeyError(f"unknown review_id: {rid}")
        current = self._reviews[rid]
        if current.verdict is not None:
            raise ValueError(f"review already decided: {current.verdict.value}")
        if verdict is CriticVerdict.REVISE and not revision_hint.strip():
            raise ValueError("revision_hint must be non-empty when verdict is revise")
        updated = CriticReview(
            review_id=current.review_id,
            bot_id=current.bot_id,
            output_text=current.output_text,
            verdict=verdict,
            critique=critique.strip(),
            revision_hint=revision_hint.strip(),
        )
        self._reviews[rid] = updated
        return updated

    def get(self, review_id: str) -> CriticReview:
        """Return the review for ``review_id``.

        Args:
            review_id: Existing review identifier.

        Returns:
            CriticReview.

        Raises:
            ValueError: When ``review_id`` is empty.
            KeyError: When ``review_id`` is unknown.
        """

        rid = self._require_nonempty(review_id, "review_id")
        if rid not in self._reviews:
            raise KeyError(f"unknown review_id: {rid}")
        return self._reviews[rid]

    def list_pending(self) -> list[CriticReview]:
        """Return all reviews that still lack a verdict (stable insertion order)."""

        return [r for r in self._reviews.values() if r.pending]

    @staticmethod
    def _require_nonempty(value: str, label: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError(f"{label} must be non-empty")
        return stripped
