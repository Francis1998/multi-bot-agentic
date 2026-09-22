"""Tool-call wave scheduler for dependency-depth parallel batches.

Schedules tool ids into waves by declared dependency depth so independent
tools can run in parallel within a wave. Distinct from ``FanInBarrierGate``
(result quorum) and ``AdaptiveConcurrencyLimiter`` (global in-flight cap).
Fills a gap vs AutoGen / CrewAI / LangGraph explicit tool-wave schedulers.
Works with GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. Never performs
network I/O.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class ToolCallWavePlan:
    """Planned tool-call waves.

    Attributes:
        waves: Tuple of waves; each wave is a sorted tuple of tool ids.
        tool_count: Total unique tools scheduled.
        wave_count: Number of waves.
        mode: ``advisory`` or ``hard``.
    """

    waves: tuple[tuple[str, ...], ...]
    tool_count: int
    wave_count: int
    mode: str


class ToolCallWaveScheduler:
    """Partition tools into parallel waves by dependency depth."""

    def __init__(self, *, mode: str = "hard") -> None:
        """Create a wave scheduler.

        Args:
            mode: ``hard`` raises on cycles/unknown deps; ``advisory`` drops
                cyclic nodes into a final wave labeled best-effort.

        Raises:
            ValueError: On invalid mode.
        """

        if mode not in {"advisory", "hard"}:
            raise ValueError("mode must be 'advisory' or 'hard'")
        self._mode = mode

    def plan(
        self,
        tools: Mapping[str, Sequence[str]],
    ) -> ToolCallWavePlan:
        """Plan waves from ``tool_id -> dependency tool ids``.

        Args:
            tools: Mapping of tool id to dependency tool ids (must exist in
                ``tools`` when mode is ``hard``).

        Returns:
            ToolCallWavePlan with sorted waves.

        Raises:
            ValueError: On empty tool id, missing deps (hard), or cycles (hard).
        """

        if not tools:
            return ToolCallWavePlan(waves=(), tool_count=0, wave_count=0, mode=self._mode)

        normalized: dict[str, set[str]] = {}
        for tool_id, deps in tools.items():
            tid = tool_id.strip()
            if not tid:
                raise ValueError("tool id must be non-empty")
            normalized[tid] = {d.strip() for d in deps if d.strip()}

        missing = {dep for deps in normalized.values() for dep in deps if dep not in normalized}
        if missing and self._mode == "hard":
            raise ValueError(f"unknown dependencies: {sorted(missing)}")
        # Drop unknown deps in advisory mode
        if missing:
            for tid in list(normalized):
                normalized[tid] = {d for d in normalized[tid] if d in normalized}

        remaining = set(normalized)
        waves: list[tuple[str, ...]] = []
        resolved: set[str] = set()

        while remaining:
            ready = sorted(tid for tid in remaining if normalized[tid].issubset(resolved))
            if not ready:
                if self._mode == "hard":
                    raise ValueError("cyclic tool dependencies")
                # advisory: dump unresolved as final best-effort wave
                waves.append(tuple(sorted(remaining)))
                remaining.clear()
                break
            waves.append(tuple(ready))
            for tid in ready:
                remaining.remove(tid)
                resolved.add(tid)

        return ToolCallWavePlan(
            waves=tuple(waves),
            tool_count=len(normalized),
            wave_count=len(waves),
            mode=self._mode,
        )
