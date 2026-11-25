"""Checkpoint save/load for resumable agent runs.

Stores checkpoints as ``EventType.CHECKPOINT`` rows in the existing sqlite
event log. This is intentionally simpler than LangGraph checkpointers: one
latest snapshot per run (observations summary, step, state, goal) without a
separate checkpoint store, thread IDs, or graph-node cursors.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from multi_bot_agentic.event_log import EventRecord, SQLiteEventLog
from multi_bot_agentic.models import EventType, Observation, RunState


@dataclass(frozen=True)
class CheckpointSnapshot:
    """Serializable resume snapshot for one agent run.

    Attributes:
        run_id: Run identifier.
        goal: Original user goal.
        step: Next zero-based loop step to execute.
        state: Lifecycle state recorded at checkpoint time.
        observations: Observations restored into the runner.
        active_bot_id: Bot whose tool scope was active at checkpoint time, if any.
        require_approval: Approval policy of the run (tool names or patterns), restored on resume.
        interrupt_id: Set when the run paused awaiting a human decision on this interrupt; ``step``
            is then the paused step, whose decision is recorded but not yet acted on.
    """

    run_id: str
    goal: str
    step: int
    state: RunState
    observations: tuple[Observation, ...]
    active_bot_id: str | None = None
    require_approval: tuple[str, ...] = ()
    interrupt_id: str | None = None

    def to_payload(self) -> dict[str, Any]:
        """Return a JSON-serializable checkpoint payload.

        Returns:
            Payload suitable for the event log.
        """

        payload: dict[str, Any] = {
            "goal": self.goal,
            "step": self.step,
            "state": self.state.value,
            "observations": [observation.to_dict() for observation in self.observations],
        }
        if self.active_bot_id is not None:
            payload["active_bot_id"] = self.active_bot_id
        if self.require_approval:
            payload["require_approval"] = sorted(self.require_approval)
        if self.interrupt_id is not None:
            payload["interrupt_id"] = self.interrupt_id
        return payload


def observation_from_dict(payload: dict[str, Any]) -> Observation:
    """Rebuild an observation from a persisted dictionary.

    Args:
        payload: Observation dictionary from a checkpoint or event.

    Returns:
        Reconstructed observation.
    """

    kwargs: dict[str, Any] = {
        "source": str(payload["source"]),
        "content": str(payload["content"]),
        "metadata": dict(payload.get("metadata", {})),
    }
    if payload.get("observation_id"):
        kwargs["observation_id"] = str(payload["observation_id"])
    return Observation(**kwargs)


def save_checkpoint(
    event_log: SQLiteEventLog,
    *,
    run_id: str,
    goal: str,
    step: int,
    state: RunState,
    observations: tuple[Observation, ...],
    active_bot_id: str | None = None,
    require_approval: Iterable[str] = (),
    interrupt_id: str | None = None,
) -> CheckpointSnapshot:
    """Persist a checkpoint event and return the snapshot.

    Args:
        event_log: Durable event log.
        run_id: Run identifier.
        goal: User goal.
        step: Next step index to resume from.
        state: State at checkpoint time.
        observations: Observations to restore on resume.
        active_bot_id: Bot whose tool scope is active, restored on resume.
        require_approval: Approval policy of the run, restored on resume.
        interrupt_id: Interrupt the run is paused at, if any.

    Returns:
        Saved checkpoint snapshot.
    """

    snapshot = CheckpointSnapshot(
        run_id=run_id,
        goal=goal,
        step=step,
        state=state,
        observations=observations,
        active_bot_id=active_bot_id,
        require_approval=tuple(sorted(set(require_approval))),
        interrupt_id=interrupt_id,
    )
    event_log.append(run_id, state, EventType.CHECKPOINT, snapshot.to_payload())
    return snapshot


def load_latest_checkpoint(event_log: SQLiteEventLog, run_id: str) -> CheckpointSnapshot | None:
    """Load the latest checkpoint for a run.

    Args:
        event_log: Durable event log.
        run_id: Run identifier.

    Returns:
        Latest checkpoint snapshot, or ``None`` when none exists.
    """

    latest: CheckpointSnapshot | None = None
    for event in event_log.list_events(run_id):
        if event.event_type != EventType.CHECKPOINT.value:
            continue
        latest = _snapshot(run_id, event.payload)
    return latest


def _snapshot(run_id: str, payload: dict[str, Any]) -> CheckpointSnapshot:
    """Parse a checkpoint payload."""

    observations = tuple(observation_from_dict(item) for item in payload.get("observations", []))
    active_bot_id = payload.get("active_bot_id")
    raw_policy = payload.get("require_approval")
    require_approval = tuple(str(item) for item in raw_policy) if isinstance(raw_policy, list) else ()
    interrupt_id = payload.get("interrupt_id")
    return CheckpointSnapshot(
        run_id=run_id,
        goal=str(payload.get("goal", "")),
        step=int(payload.get("step", 0)),
        state=RunState(str(payload.get("state", RunState.CREATED.value))),
        observations=observations,
        active_bot_id=str(active_bot_id) if active_bot_id is not None else None,
        require_approval=require_approval,
        interrupt_id=str(interrupt_id) if interrupt_id else None,
    )


def snapshot_from_event(event: EventRecord) -> CheckpointSnapshot:
    """Rebuild the snapshot stored by one ``checkpoint`` event.

    Parses the payload exactly like :func:`load_latest_checkpoint`, for callers that need a
    specific checkpoint rather than the latest one (for example a fork after step ``N``).

    Args:
        event: A ``checkpoint`` event.

    Returns:
        The checkpoint snapshot.

    Raises:
        ValueError: If the event is not a checkpoint or its payload is malformed.
    """

    if event.event_type != EventType.CHECKPOINT.value:
        raise ValueError(f"event {event.seq} of run {event.run_id} is a {event.event_type}, not a checkpoint")
    try:
        return _snapshot(event.run_id, event.payload)
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"checkpoint event {event.seq} of run {event.run_id} is malformed: {error}") from error
