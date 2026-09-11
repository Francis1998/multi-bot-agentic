"""Adaptive global in-flight concurrency limiter for multi-bot tool loops.

Caps concurrent tool executions process-wide and optionally shrinks the
effective limit when releases report failures, recovering on successes.
Distinct from ``RateLimitedToolRunner`` (per-tool sliding time window) and
``ParallelFanOut`` (batch ``max_workers``) — this is a thin, stdlib-only
in-flight guard suitable for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x /
Kimi K2 loops. Fills a gap vs AutoGen unbounded tool fanout.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class ConcurrencySnapshot:
    """Point-in-time view of limiter state.

    Attributes:
        in_flight: Current number of acquired slots still held.
        effective_limit: Current concurrency cap (may be below max when adaptive).
        error_streak: Consecutive unsuccessful releases since the last success.
    """

    in_flight: int
    effective_limit: int
    error_streak: int


class AdaptiveConcurrencyLimiter:
    """Global in-flight tool cap with optional adaptive shrink on errors.

    Caller-driven v1: wrap tool execute with ``acquire`` / ``release``. Does not
    wire into the runner automatically.

    Args:
        max_in_flight: Initial and maximum concurrent slots (must be >= 1).
        min_in_flight: Floor for the adaptive effective limit (must be >= 1
            and <= ``max_in_flight``).
        adaptive: When True, unsuccessful releases may shrink
            ``effective_limit`` toward ``min_in_flight``, and successful
            releases may grow it back toward ``max_in_flight``.
    """

    def __init__(
        self,
        max_in_flight: int,
        *,
        min_in_flight: int = 1,
        adaptive: bool = True,
    ) -> None:
        if max_in_flight < 1:
            raise ValueError("max_in_flight must be >= 1")
        if min_in_flight < 1:
            raise ValueError("min_in_flight must be >= 1")
        if min_in_flight > max_in_flight:
            raise ValueError("min_in_flight must be <= max_in_flight")
        self._max_in_flight = max_in_flight
        self._min_in_flight = min_in_flight
        self._adaptive = adaptive
        self._effective_limit = max_in_flight
        self._in_flight = 0
        self._error_streak = 0
        self._condition = threading.Condition()

    @property
    def max_in_flight(self) -> int:
        """Return configured maximum in-flight slots."""

        return self._max_in_flight

    @property
    def min_in_flight(self) -> int:
        """Return configured minimum effective limit."""

        return self._min_in_flight

    @property
    def adaptive(self) -> bool:
        """Return whether adaptive shrink/recover is enabled."""

        return self._adaptive

    def acquire(self, blocking: bool = True, timeout: float | None = None) -> bool:
        """Acquire one in-flight slot, waiting when at the effective limit.

        Args:
            blocking: When False, return immediately if no slot is available.
            timeout: Optional max seconds to wait when ``blocking`` is True.
                ``None`` waits indefinitely.

        Returns:
            True when a slot was acquired; False when non-blocking or timed out.

        Raises:
            ValueError: When ``timeout`` is negative.
        """

        if timeout is not None and timeout < 0:
            raise ValueError("timeout must be >= 0")

        with self._condition:
            if not blocking:
                if self._in_flight >= self._effective_limit:
                    return False
                self._in_flight += 1
                return True

            if timeout is None:
                while self._in_flight >= self._effective_limit:
                    self._condition.wait()
                self._in_flight += 1
                return True

            deadline_at = time.monotonic() + timeout
            while self._in_flight >= self._effective_limit:
                remaining = deadline_at - time.monotonic()
                if remaining <= 0:
                    return False
                if not self._condition.wait(timeout=remaining):
                    return False
            self._in_flight += 1
            return True

    def release(self, *, success: bool = True) -> None:
        """Release one in-flight slot and optionally adapt the limit.

        Args:
            success: When False, counts toward the error streak and may shrink
                the effective limit if adaptive mode is enabled. When True,
                clears the error streak and may grow the effective limit back
                toward ``max_in_flight``.

        Raises:
            RuntimeError: When releasing with nothing in flight.
        """

        with self._condition:
            if self._in_flight <= 0:
                raise RuntimeError("release called with nothing in flight")
            self._in_flight -= 1
            if success:
                self._error_streak = 0
                if self._adaptive and self._effective_limit < self._max_in_flight:
                    self._effective_limit += 1
            else:
                self._error_streak += 1
                if self._adaptive and self._effective_limit > self._min_in_flight:
                    self._effective_limit -= 1
            self._condition.notify_all()

    def snapshot(self) -> ConcurrencySnapshot:
        """Return a frozen snapshot of current limiter state.

        Returns:
            ConcurrencySnapshot with in_flight, effective_limit, and error_streak.
        """

        with self._condition:
            return ConcurrencySnapshot(
                in_flight=self._in_flight,
                effective_limit=self._effective_limit,
                error_streak=self._error_streak,
            )
