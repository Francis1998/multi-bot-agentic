"""Per-tool call latency tracker with advisory p50/p95 percentiles.

Records latency samples per tool name and reports percentile stats.
Never kills, cancels, or blocks tools — callers decide how to react.
Distinct from ``RunDeadlineWatchdog`` (wall-clock run deadline) and
``AdaptiveConcurrencyLimiter`` (in-flight caps) — this is a thin,
stdlib-only per-tool latency advisory for GPT-5.5 / Claude Sonnet 4.6 /
Gemini 3.x / Kimi K2 agent loops. Fills a gap vs AutoGen/CrewAI/LangGraph,
which often lack a first-class local p50/p95 tool-latency store separate
from tracing backends.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass


@dataclass(frozen=True)
class ToolLatencyStats:
    """Snapshot of latency samples for one tool.

    Attributes:
        tool_name: Tool identifier.
        sample_count: Number of retained samples.
        p50_ms: Median latency in milliseconds, or None when empty.
        p95_ms: 95th-percentile latency in milliseconds, or None when empty.
        last_ms: Most recently recorded latency, or None when empty.
    """

    tool_name: str
    sample_count: int
    p50_ms: float | None
    p95_ms: float | None
    last_ms: float | None


class ToolCallLatencyTracker:
    """Per-tool latency sample store with advisory p50/p95.

    Caller-driven v1: ``record`` after each tool call, ``stats`` to inspect,
    ``reset`` to clear. Never performs network I/O or terminates tools.
    """

    def __init__(self, *, max_samples_per_tool: int = 256) -> None:
        """Create a latency tracker.

        Args:
            max_samples_per_tool: Positive ring-buffer capacity per tool.

        Raises:
            ValueError: When ``max_samples_per_tool`` is not positive.
        """

        if max_samples_per_tool < 1:
            raise ValueError("max_samples_per_tool must be >= 1")
        self._max_samples = int(max_samples_per_tool)
        self._samples: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=self._max_samples))

    @property
    def max_samples_per_tool(self) -> int:
        """Configured ring-buffer capacity per tool."""

        return self._max_samples

    def record(self, tool_name: str, latency_ms: float) -> ToolLatencyStats:
        """Append a latency sample for ``tool_name`` and return stats.

        Args:
            tool_name: Tool identifier (non-empty).
            latency_ms: Non-negative latency in milliseconds.

        Returns:
            ToolLatencyStats after recording.

        Raises:
            ValueError: When ``tool_name`` is empty or ``latency_ms`` is negative.
        """

        name = self._require_tool(tool_name)
        if latency_ms < 0:
            raise ValueError("latency_ms must be >= 0")
        self._samples[name].append(float(latency_ms))
        return self._stats(name)

    def stats(self, tool_name: str) -> ToolLatencyStats:
        """Return current latency stats without recording.

        Args:
            tool_name: Tool identifier (non-empty).

        Returns:
            ToolLatencyStats (empty sample_count when unseen).

        Raises:
            ValueError: When ``tool_name`` is empty.
        """

        name = self._require_tool(tool_name)
        return self._stats(name)

    def reset(self, tool_name: str) -> bool:
        """Clear retained samples for ``tool_name``.

        Args:
            tool_name: Tool identifier (non-empty).

        Returns:
            True when samples were cleared; False on miss.

        Raises:
            ValueError: When ``tool_name`` is empty.
        """

        name = self._require_tool(tool_name)
        if name not in self._samples:
            return False
        del self._samples[name]
        return True

    def _stats(self, tool_name: str) -> ToolLatencyStats:
        samples = self._samples.get(tool_name)
        if not samples:
            return ToolLatencyStats(
                tool_name=tool_name,
                sample_count=0,
                p50_ms=None,
                p95_ms=None,
                last_ms=None,
            )
        ordered = sorted(samples)
        return ToolLatencyStats(
            tool_name=tool_name,
            sample_count=len(ordered),
            p50_ms=self._percentile(ordered, 50),
            p95_ms=self._percentile(ordered, 95),
            last_ms=float(samples[-1]),
        )

    @staticmethod
    def _percentile(ordered: list[float], pct: int) -> float:
        """Nearest-rank percentile on a non-empty ascending list."""

        n = len(ordered)
        # ceil(pct/100 * n) via integer arithmetic, clamped to [1, n]
        idx = min(n, max(1, (pct * n + 99) // 100)) - 1
        return float(ordered[idx])

    @staticmethod
    def _require_tool(tool_name: str) -> str:
        stripped = tool_name.strip()
        if not stripped:
            raise ValueError("tool_name must be non-empty")
        return stripped
