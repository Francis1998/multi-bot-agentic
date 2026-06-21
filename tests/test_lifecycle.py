"""Tests for lifecycle state-machine behavior."""

from __future__ import annotations

import pytest

from multi_bot_agentic.lifecycle import InvalidTransitionError, RunStateMachine
from multi_bot_agentic.models import RunState


def test_lifecycle_allows_observe_decide_act_path() -> None:
    """A normal run can move through Observe -> Decide -> Act."""

    machine = RunStateMachine()

    assert machine.transition_to(RunState.OBSERVING) == (RunState.CREATED, RunState.OBSERVING)
    assert machine.transition_to(RunState.DECIDING) == (RunState.OBSERVING, RunState.DECIDING)
    assert machine.transition_to(RunState.ACTING) == (RunState.DECIDING, RunState.ACTING)


def test_lifecycle_rejects_invalid_terminal_transition() -> None:
    """Terminal states cannot transition back into active execution."""

    machine = RunStateMachine(RunState.SUCCEEDED)

    with pytest.raises(InvalidTransitionError):
        machine.transition_to(RunState.OBSERVING)
