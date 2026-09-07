"""Parallel fan-out helpers for multi-bot task batches.

Runs a caller-supplied worker over a small task list with a thread pool, then
merges answers in input order. Workers are plain callables — no AgentRunner or
LLM calls are required — so GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2
integrations can inject their own adapters in tests or production.

Compared with CrewAI/AutoGen concurrent crews or LangGraph parallel nodes, this
module is intentionally thin: capped tasks, deterministic result ordering, and
exception → ``ok=False`` mapping without a graph runtime.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass


@dataclass(frozen=True)
class FanOutTask:
    """One unit of work for parallel execution.

    Attributes:
        task_id: Stable identifier preserved in results.
        goal: Human-readable goal text for the worker.
        bot_id: Optional bot hint for multi-bot routing.
    """

    task_id: str
    goal: str
    bot_id: str | None = None


@dataclass(frozen=True)
class FanOutResult:
    """Outcome of one fan-out task.

    Attributes:
        task_id: Matching task identifier.
        ok: Whether the worker succeeded.
        answer: Worker answer text (empty on hard failure).
        error: Error message when ``ok`` is False.
    """

    task_id: str
    ok: bool
    answer: str
    error: str | None = None


class ParallelFanOut:
    """Run capped task batches with a thread pool.

    Args:
        max_workers: Thread pool size (minimum 1).
        max_tasks: Hard cap on tasks accepted per ``run`` call.
    """

    def __init__(self, *, max_workers: int = 4, max_tasks: int = 8) -> None:
        if max_workers < 1:
            raise ValueError("max_workers must be >= 1")
        if max_tasks < 1:
            raise ValueError("max_tasks must be >= 1")
        self._max_workers = max_workers
        self._max_tasks = max_tasks

    def run(
        self,
        tasks: Sequence[FanOutTask],
        worker: Callable[[FanOutTask], FanOutResult],
    ) -> tuple[FanOutResult, ...]:
        """Execute ``worker`` for each task and return results in input order.

        Args:
            tasks: Tasks to run (length must be ``<= max_tasks``).
            worker: Callable that maps a task to a result.

        Returns:
            Results aligned with the input task order.

        Raises:
            ValueError: When the task list exceeds ``max_tasks``.
        """

        if len(tasks) > self._max_tasks:
            raise ValueError(f"max_tasks exceeded ({self._max_tasks})")
        if not tasks:
            return ()

        ordered: list[FanOutResult | None] = [None] * len(tasks)
        workers = min(self._max_workers, len(tasks))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_map = {executor.submit(self._invoke, worker, task): index for index, task in enumerate(tasks)}
            for future in as_completed(future_map):
                index = future_map[future]
                ordered[index] = future.result()
        return tuple(result for result in ordered if result is not None)

    def merge_answers(self, results: Sequence[FanOutResult], *, separator: str = "\n\n") -> str:
        """Join successful answers in order, skipping failures.

        Args:
            results: Fan-out results (usually from ``run``).
            separator: Text inserted between answers.

        Returns:
            Merged answer string (empty when no successful answers).
        """

        parts = [result.answer for result in results if result.ok and result.answer]
        return separator.join(parts)

    @staticmethod
    def _invoke(worker: Callable[[FanOutTask], FanOutResult], task: FanOutTask) -> FanOutResult:
        """Call ``worker`` and map unexpected exceptions to failed results."""

        try:
            return worker(task)
        except Exception as exc:
            return FanOutResult(task_id=task.task_id, ok=False, answer="", error=str(exc) or exc.__class__.__name__)
