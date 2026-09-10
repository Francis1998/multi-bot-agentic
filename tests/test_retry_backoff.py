"""Tests for ToolRetryBackoffPolicy."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

import pytest

from multi_bot_agentic.retry_backoff import ToolRetryBackoffPolicy

if TYPE_CHECKING:
    from _pytest.capture import CaptureFixture
    from _pytest.fixtures import FixtureRequest
    from _pytest.logging import LogCaptureFixture
    from _pytest.monkeypatch import MonkeyPatch
    from pytest_mock.plugin import MockerFixture


def test_invalid_max_attempts_raises() -> None:
    """max_attempts < 1 raises ValueError."""

    with pytest.raises(ValueError, match="max_attempts"):
        ToolRetryBackoffPolicy(max_attempts=0)


def test_next_delay_exhausts() -> None:
    """Final attempt does not retry."""

    policy = ToolRetryBackoffPolicy(max_attempts=2, jitter=False, base_seconds=1.0)
    first = policy.next_delay(1)
    assert first.should_retry is True
    assert first.sleep_seconds == 1.0
    second = policy.next_delay(2)
    assert second.should_retry is False
    assert second.sleep_seconds == 0.0


def test_jitter_bounded() -> None:
    """Full jitter stays within [0, raw delay]."""

    rng = random.Random(0)
    policy = ToolRetryBackoffPolicy(
        max_attempts=5,
        base_seconds=2.0,
        multiplier=2.0,
        max_seconds=10.0,
        jitter=True,
        rng=rng,
    )
    decision = policy.next_delay(1)
    assert decision.should_retry is True
    assert 0.0 <= decision.sleep_seconds <= 2.0


def test_run_retries_then_succeeds() -> None:
    """run() retries transient failures then returns."""

    sleeps: list[float] = []
    calls = {"n": 0}

    def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("transient")
        return "ok"

    policy = ToolRetryBackoffPolicy(
        max_attempts=3,
        jitter=False,
        base_seconds=0.1,
        rng=random.Random(1),
    )
    assert policy.run(flaky, sleeper=sleeps.append) == "ok"
    assert calls["n"] == 3
    assert len(sleeps) == 2


def test_run_raises_last_error() -> None:
    """run() re-raises the last exception when exhausted."""

    policy = ToolRetryBackoffPolicy(max_attempts=2, jitter=False, base_seconds=0.01)

    def always_fail() -> None:
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        policy.run(always_fail, sleeper=lambda _s: None)
