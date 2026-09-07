"""Tests for ParallelFanOut."""

from __future__ import annotations

import threading
import time

import pytest

from multi_bot_agentic.fanout import FanOutResult, FanOutTask, ParallelFanOut


def test_run_preserves_input_order_and_merges_answers() -> None:
    """Results stay aligned with input order even when workers finish out of order."""

    release_slow = threading.Event()

    def worker(task: FanOutTask) -> FanOutResult:
        if task.task_id == "slow":
            release_slow.wait(timeout=2.0)
            time.sleep(0.01)
        else:
            release_slow.set()
        return FanOutResult(task_id=task.task_id, ok=True, answer=f"ans-{task.task_id}")

    fanout = ParallelFanOut(max_workers=2, max_tasks=4)
    tasks = (
        FanOutTask(task_id="slow", goal="take time", bot_id="a"),
        FanOutTask(task_id="fast", goal="finish first", bot_id="b"),
    )
    results = fanout.run(tasks, worker)

    assert [item.task_id for item in results] == ["slow", "fast"]
    assert all(item.ok for item in results)
    assert fanout.merge_answers(results) == "ans-slow\n\nans-fast"
    assert fanout.merge_answers(results, separator=" | ") == "ans-slow | ans-fast"


def test_run_maps_worker_exceptions_to_failed_results() -> None:
    """Unhandled worker exceptions become ok=False results."""

    def worker(task: FanOutTask) -> FanOutResult:
        if task.task_id == "boom":
            raise RuntimeError("worker exploded")
        return FanOutResult(task_id=task.task_id, ok=True, answer="ok")

    fanout = ParallelFanOut(max_workers=2)
    results = fanout.run(
        (
            FanOutTask(task_id="ok", goal="fine"),
            FanOutTask(task_id="boom", goal="fail"),
        ),
        worker,
    )
    assert results[0].ok is True
    assert results[1].ok is False
    assert results[1].error == "worker exploded"
    assert fanout.merge_answers(results) == "ok"


def test_run_rejects_too_many_tasks() -> None:
    """Task lists beyond max_tasks raise ValueError."""

    fanout = ParallelFanOut(max_tasks=1)
    with pytest.raises(ValueError, match="max_tasks"):
        fanout.run(
            (
                FanOutTask(task_id="1", goal="a"),
                FanOutTask(task_id="2", goal="b"),
            ),
            lambda task: FanOutResult(task_id=task.task_id, ok=True, answer="x"),
        )


def test_run_empty_tasks_returns_empty_tuple() -> None:
    """An empty task list returns an empty result tuple."""

    fanout = ParallelFanOut()
    assert fanout.run((), lambda task: FanOutResult(task_id=task.task_id, ok=True, answer="x")) == ()


def test_constructor_rejects_invalid_bounds() -> None:
    """Invalid constructor bounds raise ValueError."""

    with pytest.raises(ValueError, match="max_workers"):
        ParallelFanOut(max_workers=0)
    with pytest.raises(ValueError, match="max_tasks"):
        ParallelFanOut(max_tasks=0)
