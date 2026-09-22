"""Deterministic run seed guard for reproducible multi-bot runs.

Pins and validates a run seed so offline replays stay deterministic. Distinct
from ``RunReplayDiff`` (event comparison) and ``RunDeadlineWatchdog`` (wall
clock). Fills a gap vs AutoGen / CrewAI / LangGraph reproducibility knobs.
Works with GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. Never performs
network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DeterministicRunSeedStatus:
    """Status of a pinned run seed.

    Attributes:
        run_id: Run identifier.
        seed: Pinned integer seed.
        matched: True when observed seed equals pinned seed.
        mode: ``advisory`` or ``hard``.
        allowed: True when matched, or always in advisory when mismatched.
    """

    run_id: str
    seed: int
    matched: bool
    mode: str
    allowed: bool


class DeterministicRunSeedGuard:
    """Pin and validate deterministic seeds per run id."""

    def __init__(self, *, mode: str = "hard") -> None:
        """Create a seed guard.

        Args:
            mode: ``hard`` blocks mismatches; ``advisory`` always allows.

        Raises:
            ValueError: On invalid mode.
        """

        if mode not in {"advisory", "hard"}:
            raise ValueError("mode must be 'advisory' or 'hard'")
        self._mode = mode
        self._seeds: dict[str, int] = {}

    def pin(self, run_id: str, seed: int) -> DeterministicRunSeedStatus:
        """Pin ``seed`` for ``run_id`` (overwrites prior pin)."""

        rid = run_id.strip()
        if not rid:
            raise ValueError("run_id must be non-empty")
        if not isinstance(seed, int) or isinstance(seed, bool):
            raise ValueError("seed must be an int")
        self._seeds[rid] = seed
        return DeterministicRunSeedStatus(
            run_id=rid,
            seed=seed,
            matched=True,
            mode=self._mode,
            allowed=True,
        )

    def check(self, run_id: str, seed: int) -> DeterministicRunSeedStatus:
        """Validate observed ``seed`` against the pinned value."""

        rid = run_id.strip()
        if not rid:
            raise ValueError("run_id must be non-empty")
        if not isinstance(seed, int) or isinstance(seed, bool):
            raise ValueError("seed must be an int")
        if rid not in self._seeds:
            raise ValueError(f"run_id not pinned: {rid}")
        pinned = self._seeds[rid]
        matched = seed == pinned
        allowed = bool(matched or self._mode == "advisory")
        return DeterministicRunSeedStatus(
            run_id=rid,
            seed=pinned,
            matched=matched,
            mode=self._mode,
            allowed=allowed,
        )
