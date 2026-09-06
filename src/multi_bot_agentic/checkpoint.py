"""Checkpoint save/load for resumable agent runs.

Stores checkpoints as ``EventType.CHECKPOINT`` rows in the existing sqlite
event log. This is intentionally simpler than LangGraph checkpointers: one
latest snapshot per run (observations summary, step, state, goal) without a
separate checkpoint store, thread IDs, or graph-node cursors.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from multi_bot_agentic.event_log import SQLiteEventLog
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
    """

    run_id: str
    goal: str
    step: int
    state: RunState
    observations: tuple[Observation, ...]

    def to_payload(self) -> dict[str, Any]:
        """Return a JSON-serializable checkpoint payload.

        Returns:
            Payload suitable for the event log.
        """

        return {
            "goal": self.goal,
            "step": self.step,
            "state": self.state.value,
            "observations": [observation.to_dict() for observation in self.observations],
        }


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
) -> CheckpointSnapshot:
    """Persist a checkpoint event and return the snapshot.

    Args:
        event_log: Durable event log.
        run_id: Run identifier.
        goal: User goal.
        step: Next step index to resume from.
        state: State at checkpoint time.
        observations: Observations to restore on resume.

    Returns:
        Saved checkpoint snapshot.
    """

    snapshot = CheckpointSnapshot(
        run_id=run_id,
        goal=goal,
        step=step,
        state=state,
        observations=observations,
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
        payload = event.payload
        observations = tuple(observation_from_dict(item) for item in payload.get("observations", []))
        latest = CheckpointSnapshot(
            run_id=run_id,
            goal=str(payload.get("goal", "")),
            step=int(payload.get("step", 0)),
            state=RunState(str(payload.get("state", RunState.CREATED.value))),
            observations=observations,
        )
    return latest
