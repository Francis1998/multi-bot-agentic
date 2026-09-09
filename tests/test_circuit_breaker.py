"""Tests for ToolCircuitBreaker."""

from __future__ import annotations

import pytest

from multi_bot_agentic.circuit_breaker import (
    CircuitOpenError,
    CircuitState,
    ToolCircuitBreaker,
)


class _Clock:
    """Controllable monotonic clock."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_opens_after_n_failures() -> None:
    """Circuit opens after failure_threshold consecutive failures."""

    breaker = ToolCircuitBreaker(failure_threshold=3, cooldown_seconds=10.0)
    assert breaker.allow("echo") is True
    breaker.record_failure("echo")
    breaker.record_failure("echo")
    assert breaker.state("echo") is CircuitState.CLOSED
    breaker.record_failure("echo")
    assert breaker.state("echo") is CircuitState.OPEN
    with pytest.raises(CircuitOpenError) as exc:
        breaker.allow("echo")
    assert exc.value.details.tool_name == "echo"
    assert exc.value.details.failure_count == 3


def test_cools_down_to_half_open() -> None:
    """After cooldown, state becomes half-open and allow succeeds."""

    clock = _Clock()
    breaker = ToolCircuitBreaker(failure_threshold=1, cooldown_seconds=5.0, clock=clock)
    breaker.record_failure("echo")
    assert breaker.state("echo") is CircuitState.OPEN
    clock.now = 5.0
    assert breaker.state("echo") is CircuitState.HALF_OPEN
    assert breaker.allow("echo") is True


def test_half_open_success_closes() -> None:
    """A successful probe while half-open closes the circuit."""

    clock = _Clock()
    breaker = ToolCircuitBreaker(failure_threshold=2, cooldown_seconds=4.0, clock=clock)
    breaker.record_failure("search")
    breaker.record_failure("search")
    clock.now = 4.0
    assert breaker.allow("search") is True
    assert breaker.state("search") is CircuitState.HALF_OPEN
    breaker.record_success("search")
    assert breaker.state("search") is CircuitState.CLOSED
    assert breaker.allow("search") is True


def test_half_open_failure_reopens() -> None:
    """A failed probe while half-open reopens the circuit."""

    clock = _Clock()
    breaker = ToolCircuitBreaker(failure_threshold=1, cooldown_seconds=2.0, clock=clock)
    breaker.record_failure("echo")
    clock.now = 2.0
    assert breaker.allow("echo") is True
    breaker.record_failure("echo")
    assert breaker.state("echo") is CircuitState.OPEN


def test_invalid_config_raises() -> None:
    """Invalid constructor args raise ValueError."""

    with pytest.raises(ValueError):
        ToolCircuitBreaker(failure_threshold=0)
    with pytest.raises(ValueError):
        ToolCircuitBreaker(cooldown_seconds=0)
