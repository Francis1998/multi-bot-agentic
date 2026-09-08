"""Rate-limited tool runner wrapper.

Wraps ``ToolAdapter.execute`` with a sliding-window rate limit so multi-bot
loops cannot hammer the same tool. Distinct from ``SafetyPolicy`` step/timeout
caps and from CrewAI/AutoGen global concurrency knobs — this is a per-tool
call budget suitable for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2
tool loops.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass

from multi_bot_agentic.models import ToolInvocation, ToolResult
from multi_bot_agentic.tools.base import ToolAdapter


@dataclass(frozen=True)
class RateLimitExceeded:
    """Details about a rejected tool call.

    Attributes:
        tool_name: Tool that exceeded its budget.
        limit: Allowed calls per window.
        window_seconds: Sliding window size.
        retry_after_seconds: Suggested wait before retry.
    """

    tool_name: str
    limit: int
    window_seconds: float
    retry_after_seconds: float


class RateLimitExceededError(RuntimeError):
    """Raised when a tool call exceeds its rate budget."""

    def __init__(self, details: RateLimitExceeded) -> None:
        self.details = details
        super().__init__(
            f"rate limit exceeded for tool '{details.tool_name}' "
            f"({details.limit}/{details.window_seconds}s); "
            f"retry_after={details.retry_after_seconds:.3f}s"
        )


class RateLimitedToolRunner:
    """Execute tools under a per-tool sliding-window rate limit.

    Args:
        tools: Mapping of tool name to adapter.
        max_calls: Maximum calls allowed per tool per window.
        window_seconds: Sliding window length in seconds.
        clock: Optional monotonic clock (injectable for tests).
    """

    def __init__(
        self,
        tools: dict[str, ToolAdapter],
        *,
        max_calls: int = 8,
        window_seconds: float = 60.0,
        clock: Callable[[], float] | None = None,
    ) -> None:
        if max_calls < 1:
            raise ValueError("max_calls must be >= 1")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be > 0")
        self._tools = dict(tools)
        self._max_calls = max_calls
        self._window_seconds = window_seconds
        self._clock = clock or time.monotonic
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    @property
    def max_calls(self) -> int:
        """Return configured max_calls."""

        return self._max_calls

    @property
    def window_seconds(self) -> float:
        """Return configured window_seconds."""

        return self._window_seconds

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Execute a tool invocation if under rate limit.

        Args:
            invocation: Tool call request.

        Returns:
            ToolResult from the underlying adapter.

        Raises:
            KeyError: Unknown tool name.
            RateLimitExceededError: When the sliding window is full.
        """

        tool = self._tools.get(invocation.tool_name)
        if tool is None:
            raise KeyError(f"unknown tool: {invocation.tool_name}")

        now = float(self._clock())
        bucket = self._hits[invocation.tool_name]
        cutoff = now - self._window_seconds
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= self._max_calls:
            retry_after = max(0.0, self._window_seconds - (now - bucket[0]))
            raise RateLimitExceededError(
                RateLimitExceeded(
                    tool_name=invocation.tool_name,
                    limit=self._max_calls,
                    window_seconds=self._window_seconds,
                    retry_after_seconds=round(retry_after, 3),
                )
            )
        bucket.append(now)
        return tool.execute(invocation)

    def remaining(self, tool_name: str) -> int:
        """Return remaining calls for ``tool_name`` in the current window.

        Args:
            tool_name: Tool to inspect.

        Returns:
            Non-negative remaining call budget.
        """

        now = float(self._clock())
        bucket = self._hits[tool_name]
        cutoff = now - self._window_seconds
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        return max(0, self._max_calls - len(bucket))
