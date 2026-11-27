"""State-machine enforcement for agent runs."""

from __future__ import annotations

from dataclasses import dataclass

from multi_bot_agentic.models import RunState


class InvalidTransitionError(ValueError):
    """Raised when a run attempts an invalid lifecycle transition."""


ALLOWED_TRANSITIONS: dict[RunState, frozenset[RunState]] = {
    RunState.CREATED: frozenset({RunState.OBSERVING, RunState.CANCELLED, RunState.FAILED}),
    RunState.OBSERVING: frozenset({RunState.DECIDING, RunState.CANCELLED, RunState.FAILED}),
    RunState.DECIDING: frozenset(
        {
            RunState.ACTING,
            RunState.AWAITING_APPROVAL,
            RunState.VALIDATING,
            RunState.SUCCEEDED,
            RunState.CANCELLED,
            RunState.FAILED,
        }
    ),
    # A paused run continues by acting on an approved call, or by observing a rejection and re-planning.
    RunState.AWAITING_APPROVAL: frozenset({RunState.ACTING, RunState.OBSERVING, RunState.CANCELLED, RunState.FAILED}),
    RunState.ACTING: frozenset({RunState.OBSERVING, RunState.SUCCEEDED, RunState.CANCELLED, RunState.FAILED}),
    # A final answer checked against the output schema: valid, corrected in another round, or given up on.
    RunState.VALIDATING: frozenset(
        {RunState.SUCCEEDED, RunState.OBSERVING, RunState.OUTPUT_INVALID, RunState.CANCELLED, RunState.FAILED}
    ),
    RunState.SUCCEEDED: frozenset(),
    RunState.FAILED: frozenset(),
    RunState.CANCELLED: frozenset(),
    RunState.OUTPUT_INVALID: frozenset(),
}

TERMINAL_STATES: frozenset[RunState] = frozenset(
    {RunState.SUCCEEDED, RunState.FAILED, RunState.CANCELLED, RunState.OUTPUT_INVALID}
)


@dataclass
class RunStateMachine:
    """Explicit lifecycle state machine for a run."""

    state: RunState = RunState.CREATED

    def transition_to(self, next_state: RunState) -> tuple[RunState, RunState]:
        """Move to the next state if the transition is legal.

        Args:
            next_state: Desired next state.

        Returns:
            Previous and next state.

        Raises:
            InvalidTransitionError: If the transition is not legal.
        """

        allowed_states = ALLOWED_TRANSITIONS[self.state]
        if next_state not in allowed_states:
            raise InvalidTransitionError(f"invalid transition: {self.state.value} -> {next_state.value}")
        previous_state = self.state
        self.state = next_state
        return previous_state, next_state

    def is_terminal(self) -> bool:
        """Return whether the run is in a terminal state.

        Returns:
            True when no more actions should execute.
        """

        return self.state in TERMINAL_STATES
