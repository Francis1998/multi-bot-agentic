"""Jittered retry / backoff policy for multi-bot tool calls.

Distinct from :class:`~multi_bot_agentic.circuit_breaker.ToolCircuitBreaker`
(which opens after consecutive failures) — this policy computes sleep delays
for transient retries with optional full-jitter. Suitable for GPT-5.5 /
Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 tool loops without framework lock-in.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class RetryDecision:
    """Decision for the next retry attempt.

    Attributes:
        attempt: 1-based attempt number that just failed.
        should_retry: Whether another attempt is allowed.
        sleep_seconds: Suggested sleep before the next attempt (0 when done).
    """

    attempt: int
    should_retry: bool
    sleep_seconds: float


class ToolRetryBackoffPolicy:
    """Exponential backoff with optional full jitter for tool retries.

    Args:
        max_attempts: Maximum attempts including the first try (>= 1).
        base_seconds: Initial backoff base (> 0).
        multiplier: Exponential growth factor (>= 1).
        max_seconds: Cap on computed delay (> 0).
        jitter: When True, apply full jitter in ``[0, delay]``.
        rng: Optional random.Random-like for deterministic tests.
    """

    def __init__(
        self,
        *,
        max_attempts: int = 3,
        base_seconds: float = 0.5,
        multiplier: float = 2.0,
        max_seconds: float = 30.0,
        jitter: bool = True,
        rng: random.Random | None = None,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if base_seconds <= 0:
            raise ValueError("base_seconds must be > 0")
        if multiplier < 1:
            raise ValueError("multiplier must be >= 1")
        if max_seconds <= 0:
            raise ValueError("max_seconds must be > 0")
        self._max_attempts = max_attempts
        self._base_seconds = base_seconds
        self._multiplier = multiplier
        self._max_seconds = max_seconds
        self._jitter = jitter
        self._rng = rng if rng is not None else random.Random()

    @property
    def max_attempts(self) -> int:
        """Return configured max_attempts."""

        return self._max_attempts

    def next_delay(self, attempt: int) -> RetryDecision:
        """Compute the retry decision after a failed attempt.

        Args:
            attempt: 1-based attempt number that just failed.

        Returns:
            RetryDecision with should_retry and sleep_seconds.

        Raises:
            ValueError: When attempt is not a positive int.
        """

        if not isinstance(attempt, int) or isinstance(attempt, bool) or attempt < 1:
            raise ValueError("attempt must be a positive int")

        if attempt >= self._max_attempts:
            return RetryDecision(attempt=attempt, should_retry=False, sleep_seconds=0.0)

        raw = min(
            self._max_seconds,
            self._base_seconds * (self._multiplier ** (attempt - 1)),
        )
        sleep = float(self._rng.uniform(0.0, raw)) if self._jitter else float(raw)
        return RetryDecision(
            attempt=attempt,
            should_retry=True,
            sleep_seconds=round(sleep, 6),
        )

    def run(
        self,
        fn: Callable[[], object],
        *,
        sleeper: Callable[[float], None] | None = None,
    ) -> object:
        """Execute ``fn`` with retries under this policy.

        Args:
            fn: Zero-arg callable to invoke.
            sleeper: Optional sleep function (defaults to ``time.sleep``).

        Returns:
            The successful return value of ``fn``.

        Raises:
            Exception: The last exception raised by ``fn`` when retries exhaust.
        """

        import time

        sleep_fn = sleeper or time.sleep
        last_exc: BaseException | None = None
        for attempt in range(1, self._max_attempts + 1):
            try:
                return fn()
            except Exception as exc:
                last_exc = exc
                decision = self.next_delay(attempt)
                if not decision.should_retry:
                    break
                sleep_fn(decision.sleep_seconds)
        assert last_exc is not None
        raise last_exc
