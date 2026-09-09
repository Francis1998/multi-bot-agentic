"""Per-tool circuit breaker for multi-bot tool loops.

Isolates failures per tool name with classic open / half-open / closed states.
Distinct from LangGraph retry policies and CrewAI crew-level failure handling —
this is a thin, stdlib-only guard suitable for GPT-5.5 / Claude Sonnet 4.6 /
Gemini 3.x / Kimi K2 tool loops.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum


class CircuitState(str, Enum):
    """Circuit breaker state for a single tool."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass(frozen=True)
class CircuitOpenInfo:
    """Details about a rejected call while the circuit is open.

    Attributes:
        tool_name: Tool whose circuit is open.
        failure_count: Consecutive failures that tripped the breaker.
        cooldown_seconds: Configured cooldown window.
        retry_after_seconds: Suggested wait before the next probe.
    """

    tool_name: str
    failure_count: int
    cooldown_seconds: float
    retry_after_seconds: float


class CircuitOpenError(RuntimeError):
    """Raised when ``allow`` is called while the circuit is open."""

    def __init__(self, details: CircuitOpenInfo) -> None:
        self.details = details
        super().__init__(
            f"circuit open for tool '{details.tool_name}' "
            f"(failures={details.failure_count}); "
            f"retry_after={details.retry_after_seconds:.3f}s"
        )


@dataclass
class _ToolBreaker:
    """Mutable per-tool breaker state."""

    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    opened_at: float | None = None


class ToolCircuitBreaker:
    """Per-tool failure isolation with open / half-open / closed states.

    Args:
        failure_threshold: Consecutive failures required to open the circuit.
        cooldown_seconds: Seconds to stay open before allowing a half-open probe.
        clock: Optional monotonic clock (injectable for tests).
    """

    def __init__(
        self,
        *,
        failure_threshold: int = 5,
        cooldown_seconds: float = 30.0,
        clock: Callable[[], float] | None = None,
    ) -> None:
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be >= 1")
        if cooldown_seconds <= 0:
            raise ValueError("cooldown_seconds must be > 0")
        self._failure_threshold = failure_threshold
        self._cooldown_seconds = cooldown_seconds
        self._clock = clock or time.monotonic
        self._tools: dict[str, _ToolBreaker] = {}

    @property
    def failure_threshold(self) -> int:
        """Return configured failure_threshold."""

        return self._failure_threshold

    @property
    def cooldown_seconds(self) -> float:
        """Return configured cooldown_seconds."""

        return self._cooldown_seconds

    def state(self, tool_name: str) -> CircuitState:
        """Return the current circuit state for a tool.

        Args:
            tool_name: Tool identifier.

        Returns:
            CircuitState for the tool (defaults to closed when unseen).
        """

        breaker = self._tools.get(tool_name)
        if breaker is None:
            return CircuitState.CLOSED
        self._maybe_transition_to_half_open(breaker)
        return breaker.state

    def allow(self, tool_name: str) -> bool:
        """Return True when the tool may be invoked; raise when open.

        Args:
            tool_name: Tool identifier.

        Returns:
            True when the circuit is closed or half-open.

        Raises:
            CircuitOpenError: When the circuit is still open.
        """

        breaker = self._tools.setdefault(tool_name, _ToolBreaker())
        self._maybe_transition_to_half_open(breaker)
        if breaker.state is CircuitState.OPEN:
            now = float(self._clock())
            opened_at = breaker.opened_at if breaker.opened_at is not None else now
            retry_after = max(0.0, self._cooldown_seconds - (now - opened_at))
            raise CircuitOpenError(
                CircuitOpenInfo(
                    tool_name=tool_name,
                    failure_count=breaker.failure_count,
                    cooldown_seconds=self._cooldown_seconds,
                    retry_after_seconds=round(retry_after, 3),
                )
            )
        return True

    def record_failure(self, tool_name: str) -> None:
        """Record a tool failure and open the circuit when threshold is hit.

        Args:
            tool_name: Tool identifier.
        """

        breaker = self._tools.setdefault(tool_name, _ToolBreaker())
        breaker.failure_count += 1
        if breaker.state is CircuitState.HALF_OPEN or breaker.failure_count >= self._failure_threshold:
            breaker.state = CircuitState.OPEN
            breaker.opened_at = float(self._clock())

    def record_success(self, tool_name: str) -> None:
        """Record a tool success and close the circuit.

        Args:
            tool_name: Tool identifier.
        """

        breaker = self._tools.setdefault(tool_name, _ToolBreaker())
        breaker.state = CircuitState.CLOSED
        breaker.failure_count = 0
        breaker.opened_at = None

    def _maybe_transition_to_half_open(self, breaker: _ToolBreaker) -> None:
        """Move from open to half-open once the cooldown has elapsed."""

        if breaker.state is not CircuitState.OPEN or breaker.opened_at is None:
            return
        now = float(self._clock())
        if now - breaker.opened_at >= self._cooldown_seconds:
            breaker.state = CircuitState.HALF_OPEN
