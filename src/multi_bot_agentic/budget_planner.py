"""Token/cost-aware step planner for multi-bot ODA loops.

Caps agent steps using both a step budget and an estimated token budget before
LLM calls. Distinct from LangGraph unbounded graph loops — this is a thin,
stdlib-only preflight suitable for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x /
Kimi K2 runs.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BudgetPlan:
    """Result of planning an agent run under step and token caps.

    Attributes:
        allowed_steps: Steps permitted under the tighter of the two budgets.
        reason: Human-readable explanation of which knob bound the plan.
    """

    allowed_steps: int
    reason: str


class BudgetedStepPlanner:
    """Plan and track step/token budgets before LLM calls.

    Caller-driven v1: call ``plan`` before a run, then ``reserve`` after each
    model/tool step consumes tokens.
    """

    def __init__(self) -> None:
        self._remaining_tokens = 0
        self._remaining_steps = 0

    def plan(
        self,
        *,
        max_steps: int,
        max_tokens: int,
        estimated_tokens_per_step: int,
    ) -> BudgetPlan:
        """Compute allowed steps under step and token budgets.

        Args:
            max_steps: Hard step cap for the run.
            max_tokens: Total token budget for the run.
            estimated_tokens_per_step: Expected tokens consumed per step.

        Returns:
            BudgetPlan with allowed_steps and a reason string.

        Raises:
            ValueError: When any knob is not positive.
        """

        if max_steps < 1:
            raise ValueError("max_steps must be >= 1")
        if max_tokens < 1:
            raise ValueError("max_tokens must be >= 1")
        if estimated_tokens_per_step < 1:
            raise ValueError("estimated_tokens_per_step must be >= 1")

        by_tokens = max_tokens // estimated_tokens_per_step
        if by_tokens < 1:
            self._remaining_tokens = max_tokens
            self._remaining_steps = 0
            return BudgetPlan(
                allowed_steps=0,
                reason="token budget too small for one estimated step",
            )

        if by_tokens < max_steps:
            allowed = by_tokens
            reason = "limited by token budget"
        else:
            allowed = max_steps
            reason = "limited by max_steps"

        self._remaining_tokens = max_tokens
        self._remaining_steps = allowed
        return BudgetPlan(allowed_steps=allowed, reason=reason)

    def reserve(self, tokens: int) -> None:
        """Reserve tokens for a completed step and decrement remaining steps.

        Args:
            tokens: Tokens consumed by the step (non-negative).

        Raises:
            ValueError: When ``tokens`` is negative or exceeds remaining_tokens.
            RuntimeError: When no steps remain.
        """

        if tokens < 0:
            raise ValueError("tokens must be >= 0")
        if self._remaining_steps < 1:
            raise RuntimeError("no remaining steps to reserve")
        if tokens > self._remaining_tokens:
            raise ValueError("tokens exceed remaining_tokens")
        self._remaining_tokens -= tokens
        self._remaining_steps -= 1

    @property
    def remaining_tokens(self) -> int:
        """Return tokens still available after planning/reservations."""

        return self._remaining_tokens

    @property
    def remaining_steps(self) -> int:
        """Return steps still available after planning/reservations."""

        return self._remaining_steps
