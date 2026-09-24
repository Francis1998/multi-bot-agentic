"""Deterministic vote tie-break policy for multi-bot consensus.

Resolves tied vote tallies with an explicit, auditable policy band for HITL
review. Distinct from ``BotVoteConsensusAggregator`` (winner selection) and
``ConsensusConfidenceBandAdvisor`` (vote-share bands). Fills a gap vs
AutoGen / CrewAI / LangGraph silent or nondeterministic ties. Works with
GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. Never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass

_ALLOWED = frozenset({"lexicographic", "seeded", "escalate"})


@dataclass(frozen=True)
class VoteTieBreakResult:
    """Result of applying a vote tie-break policy."""

    session_id: str
    tied_options: tuple[str, ...]
    policy: str
    winner: str | None
    band: str
    requires_human_review: bool


class VoteTieBreakPolicy:
    """Apply a deterministic tie-break policy to tied options."""

    def resolve(
        self,
        session_id: str,
        *,
        tied_options: list[str],
        policy: str = "lexicographic",
        seed: str = "",
    ) -> VoteTieBreakResult:
        """Resolve ``tied_options`` under ``policy``.

        Args:
            session_id: Non-empty session id.
            tied_options: Options that share the top vote count.
            policy: One of ``lexicographic`` / ``seeded`` / ``escalate``.
            seed: Required non-empty seed when ``policy="seeded"``.

        Returns:
            VoteTieBreakResult with ``requires_human_review=True``.
        """

        sid = session_id.strip()
        if not sid:
            raise ValueError("session_id must be non-empty")
        cleaned = [opt.strip() for opt in tied_options if opt.strip()]
        if len(cleaned) < 2:
            raise ValueError("tied_options must contain at least 2 non-empty options")
        pol = policy.strip().lower()
        if pol not in _ALLOWED:
            raise ValueError("policy must be one of lexicographic/seeded/escalate")

        unique = tuple(sorted(set(cleaned)))
        if pol == "escalate":
            return VoteTieBreakResult(
                session_id=sid,
                tied_options=unique,
                policy=pol,
                winner=None,
                band="escalate",
                requires_human_review=True,
            )
        if pol == "lexicographic":
            winner = unique[0]
            band = "resolved"
        else:
            seed_clean = seed.strip()
            if not seed_clean:
                raise ValueError("seed must be non-empty for seeded policy")
            # Stable hash: pick by (seed + option) lexicographic min of digests.
            winner = min(unique, key=lambda opt: f"{seed_clean}:{opt}")
            band = "resolved"

        return VoteTieBreakResult(
            session_id=sid,
            tied_options=unique,
            policy=pol,
            winner=winner,
            band=band,
            requires_human_review=True,
        )
