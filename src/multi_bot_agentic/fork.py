"""Time-travel forks: branch a recorded run after any step and continue it.

A fork rebuilds the runtime state after step ``N`` of a recorded run from the event log alone and
starts a new run that inherits that history, optionally with a different goal, provider, bot, or
step budget. The source run is never modified.

Steps count completed Observe -> Decide -> Act iterations. The state after step ``N`` is the
latest checkpoint recorded for step ``N``: the one the runner wrote at the end of step ``N`` (its
``step`` field is ``N``, which is also the zero-based index of the next loop iteration), or the
starting checkpoint of a fork that continued after step ``N``. Without a checkpoint, step ``0`` is
the state every run starts with: the goal and nothing else.

A fork's event log starts with a ``run_forked`` lineage event, followed by copies of the source
events up to the fork point (its *inherited* events), followed by its own events: the bot switch,
if any, and a checkpoint of its starting state, so a fork that dies in its first step resumes
with its overrides. Copies keep the event type, state, and payload; they get the fork's run id,
new sequence numbers, and the time they were copied. The lineage event records SHA-256 digests
of the fork-point event and of the inherited events, so a fork's ``replay``, ``report``, and
``trace`` need only its own events.

Nothing in this module writes to the event log or calls a provider or tool:
:meth:`multi_bot_agentic.runner.AgentRunner.fork` writes the fork and runs its continuation.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any, Final

from multi_bot_agentic.bots import BotSpec
from multi_bot_agentic.checkpoint import observation_from_dict, snapshot_from_event
from multi_bot_agentic.decision import DeterministicDecisionEngine
from multi_bot_agentic.event_log import EventRecord, SQLiteEventLog
from multi_bot_agentic.models import Decision, EventType, Observation, RunState
from multi_bot_agentic.safety import SafetyError, SafetyPolicy

RUN_FORKED: Final[str] = EventType.RUN_FORKED.value
# Rule id recorded for the handoff a fork performs when ``bot_id`` switches bots.
BOT_OVERRIDE_RULE: Final[str] = "fork.bot-override"

_TERMINAL_STATES: Final[Mapping[str, str]] = {
    EventType.RUN_COMPLETED.value: RunState.SUCCEEDED.value,
    EventType.RUN_FAILED.value: RunState.FAILED.value,
    EventType.RUN_CANCELLED.value: RunState.CANCELLED.value,
}
_EVENT_TYPES: Final[frozenset[str]] = frozenset(item.value for item in EventType)
_RUN_STATES: Final[frozenset[str]] = frozenset(item.value for item in RunState)
_DIRECTIVES: Final[tuple[str, ...]] = ("TOOL", "HANDOFF", "DONE")


class ForkError(ValueError):
    """Raised when a run cannot be forked as requested. Nothing has been written."""


@dataclass(frozen=True)
class ForkLineage:
    """Where a fork branched off, read from its ``run_forked`` event.

    Attributes:
        run_id: The fork.
        seq: Sequence number of the ``run_forked`` event in the fork.
        timestamp: When the fork was created.
        parent_run_id: Run the fork branched from.
        fork_step: Steps of the parent the fork inherited; it continued after this step.
        parent_event_seq: Sequence number, in the parent, of the event that recorded the fork point.
        parent_event_sha256: :func:`event_digest` of that event.
        inherited_events: Number of parent events copied right after the ``run_forked`` event.
        prefix_sha256: :func:`prefix_digest` of those copies.
        goal: Goal the fork continued with.
        provider: Provider the fork continued with.
        bot: Bot whose tool scope the fork continued with, if any.
        max_steps: Step budget of the fork, inherited steps included.
        overrides: Settings that differ from the parent at the fork point (``goal``, ``bot``, ``provider``).
    """

    run_id: str
    seq: int
    timestamp: str
    parent_run_id: str
    fork_step: int
    parent_event_seq: int
    parent_event_sha256: str
    inherited_events: int
    prefix_sha256: str
    goal: str | None
    provider: str | None
    bot: str | None
    max_steps: int | None
    overrides: Mapping[str, Any] = field(default_factory=dict)

    def summary(self) -> dict[str, Any]:
        """Return the lineage as a JSON-serializable dictionary (the goal only when it was overridden)."""

        return {
            "parent_run_id": self.parent_run_id,
            "fork_step": self.fork_step,
            "parent_event_seq": self.parent_event_seq,
            "parent_event_sha256": self.parent_event_sha256,
            "inherited_events": self.inherited_events,
            "prefix_sha256": self.prefix_sha256,
            "provider": self.provider,
            "bot": self.bot,
            "max_steps": self.max_steps,
            "overrides": dict(self.overrides),
        }


@dataclass(frozen=True)
class HistoryStep:
    """One step of a recorded run, as listed by ``history``.

    Attributes:
        step: ``1`` for the first Observe -> Decide -> Act iteration; ``0`` is the start (goal only).
        bot: Bot active when the step decided, if any.
        action: Decision action (``None`` for step 0).
        target: Provider, tool, or bot the action targeted.
        rule_id: Rule that chose the action.
        outcome: Short result: the model's directive, the tool result, the handoff, or the run's end. A
            directive's target is model output, so it is named only when it is a tool the run called
            or a bot it ran.
        forkable: True when the state after the step was recorded, so ``fork --at-step`` accepts it.
        inherited: True when the step was copied from a parent run by a fork.
        event_seq: Sequence number of the event that recorded the state after the step.
    """

    step: int
    bot: str | None
    action: str | None
    target: str | None
    rule_id: str | None
    outcome: str
    forkable: bool
    inherited: bool
    event_seq: int | None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dictionary."""

        return {
            "step": self.step,
            "bot": self.bot,
            "action": self.action,
            "target": self.target,
            "rule_id": self.rule_id,
            "outcome": self.outcome,
            "forkable": self.forkable,
            "inherited": self.inherited,
        }


@dataclass(frozen=True)
class RunHistory:
    """The steps of one recorded run and where it came from.

    Attributes:
        run_id: Run identifier.
        goal: Goal the run worked on (a fork's own goal), if recorded.
        provider: Provider the run used (a fork's own provider), if recorded.
        final_state: ``succeeded``, ``failed``, ``cancelled``, or ``unfinished``.
        steps: Step 0 (the start) and every step that made a decision, in order.
        lineage: Where the run was forked from, or ``None`` for an original run.
    """

    run_id: str
    goal: str | None
    provider: str | None
    final_state: str
    steps: tuple[HistoryStep, ...]
    lineage: ForkLineage | None

    @property
    def last_step(self) -> int:
        """Return the number of the last recorded step (``0`` when no step ran)."""

        return self.steps[-1].step if self.steps else 0

    def forkable_steps(self) -> tuple[int, ...]:
        """Return the steps ``fork --at-step`` accepts."""

        return tuple(item.step for item in self.steps if item.forkable)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dictionary."""

        return {
            "run_id": self.run_id,
            "goal": self.goal,
            "provider": self.provider,
            "final_state": self.final_state,
            "last_step": self.last_step,
            "forkable_steps": list(self.forkable_steps()),
            "lineage": self.lineage.summary() if self.lineage is not None else None,
            "steps": [item.to_dict() for item in self.steps],
        }


@dataclass(frozen=True)
class ForkPoint:
    """The runtime state after one step of a recorded run, rebuilt from its events.

    Attributes:
        run_id: Source run.
        step: Steps completed (``0`` is the start).
        goal: Goal in effect.
        observations: Observations the next step decides on.
        bot: Bot whose tool scope was active, if any.
        event: Event that recorded the state: the latest checkpoint for the step, or the run's
            first ``run_created`` event for step 0 when there is no step-0 checkpoint.
        prefix: Source events a fork inherits: every event up to and including ``event``,
            except ancestor ``run_forked`` events whose inherited events would be cut off.
    """

    run_id: str
    step: int
    goal: str
    observations: tuple[Observation, ...]
    bot: str | None
    event: EventRecord
    prefix: tuple[EventRecord, ...]


@dataclass(frozen=True)
class ForkPlan:
    """Everything a fork will write and run, computed without writing or calling a provider.

    Attributes:
        source_run_id: Run to branch from.
        new_run_id: Run id of the fork.
        point: Reconstructed state after the fork step.
        goal: Goal the fork continues with.
        provider: Provider the fork continues with.
        bot: Bot the fork continues as, if any.
        source_bot: Bot that was active at the fork point in the source run, if any.
        allowed_tools: Tool allowlist of the continuation (the bot's scope, or the policy allowlist).
        max_steps: Step budget of the fork, inherited steps included.
        observations: Observations the fork's first own step decides on (the state plus overrides).
        handoff: ``action_result`` payload recording the bot switch, or ``None`` when the bot is unchanged.
        lineage: Payload of the fork's ``run_forked`` event.
        next_decision: Decision the fork's first own step makes (the engine is deterministic).
    """

    source_run_id: str
    new_run_id: str
    point: ForkPoint
    goal: str
    provider: str
    bot: str | None
    source_bot: str | None
    allowed_tools: frozenset[str]
    max_steps: int
    observations: tuple[Observation, ...]
    handoff: Mapping[str, Any] | None
    lineage: Mapping[str, Any]
    next_decision: Decision

    @property
    def at_step(self) -> int:
        """Return the step the fork continues after."""

        return self.point.step

    @property
    def remaining_steps(self) -> int:
        """Return the steps left in the fork's budget."""

        return self.max_steps - self.point.step

    def to_dict(self) -> dict[str, Any]:
        """Return the plan as a JSON-serializable dictionary (``fork --dry-run`` output)."""

        decision = self.next_decision
        return {
            "dry_run": True,
            "source_run_id": self.source_run_id,
            "new_run_id": self.new_run_id,
            "fork_step": self.at_step,
            "goal": self.goal,
            "provider": self.provider,
            "bot": self.bot,
            "bot_tools": sorted(self.allowed_tools) if self.bot is not None else None,
            "max_steps": self.max_steps,
            "remaining_steps": self.remaining_steps,
            "overrides": dict(self.lineage.get("overrides", {})),
            "parent_event": dict(self.lineage.get("parent_event", {})),
            "inherited_events": len(self.point.prefix),
            "prefix_sha256": self.lineage.get("prefix_sha256"),
            "observations": [
                {"source": observation.source, "content": observation.content} for observation in self.observations
            ],
            "next_decision": {
                "action": decision.action,
                "target": decision.target,
                "rule_id": decision.rationale.rule_id,
            },
        }


def event_digest(event: EventRecord) -> str:
    """Return the SHA-256 digest of an event's type, state, and payload.

    The run id, sequence number, and timestamp are left out, so a copy made by a fork has the
    same digest as its original.

    Args:
        event: Event record.

    Returns:
        Lower-case hex digest.
    """

    canonical = json.dumps(
        {"event_type": event.event_type, "state": event.state, "payload": event.payload},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def prefix_digest(events: Iterable[EventRecord]) -> str:
    """Return the SHA-256 digest of a sequence of events, in order.

    Args:
        events: Events, for example the events a fork inherits.

    Returns:
        Lower-case hex digest over each event's :func:`event_digest`.
    """

    digest = hashlib.sha256()
    for event in events:
        digest.update(event_digest(event).encode("ascii"))
    return digest.hexdigest()


def parse_lineage(event: EventRecord) -> ForkLineage | None:
    """Read a ``run_forked`` event.

    Args:
        event: Any event record.

    Returns:
        The lineage, or ``None`` for other events and malformed lineage payloads.
    """

    if event.event_type != RUN_FORKED:
        return None
    payload = event.payload
    parent = payload.get("parent_event")
    parent_event = parent if isinstance(parent, dict) else {}
    parent_run_id = _optional_str(payload.get("parent_run_id"))
    fork_step = _count(payload.get("fork_step"))
    inherited = _count(payload.get("inherited_events"))
    if parent_run_id is None or fork_step is None or inherited is None:
        return None
    overrides = payload.get("overrides")
    return ForkLineage(
        run_id=event.run_id,
        seq=event.seq,
        timestamp=event.timestamp,
        parent_run_id=parent_run_id,
        fork_step=fork_step,
        parent_event_seq=_count(parent_event.get("seq")) or 0,
        parent_event_sha256=str(parent_event.get("sha256", "")),
        inherited_events=inherited,
        prefix_sha256=str(payload.get("prefix_sha256", "")),
        goal=_optional_str(payload.get("goal")),
        provider=_optional_str(payload.get("provider")),
        bot=_optional_str(payload.get("bot")),
        max_steps=_count(payload.get("max_steps")),
        overrides=dict(overrides) if isinstance(overrides, dict) else {},
    )


def run_lineage(events: Sequence[EventRecord]) -> ForkLineage | None:
    """Return a run's own lineage: its first event, when that is a ``run_forked`` event.

    Args:
        events: Events of one run, in any order.

    Returns:
        The lineage, or ``None`` for a run that was not forked.
    """

    if not events:
        return None
    return parse_lineage(min(events, key=lambda event: event.seq))


def fork_children(events: Iterable[EventRecord]) -> dict[str, list[ForkLineage]]:
    """Group forks by the run they branched from.

    Args:
        events: Events of any runs; only each run's first event is considered.

    Returns:
        Lineages of the forks keyed by parent run id, ordered by fork step and run id.
    """

    children: dict[str, list[ForkLineage]] = {}
    for event in events:
        if event.seq != 1:
            continue
        lineage = parse_lineage(event)
        if lineage is not None:
            children.setdefault(lineage.parent_run_id, []).append(lineage)
    for forks in children.values():
        forks.sort(key=lambda item: (item.fork_step, item.run_id))
    return children


def inherited_events_intact(events: Sequence[EventRecord], lineage: ForkLineage) -> bool:
    """Check that a fork's inherited events still match the digest recorded when it was forked.

    Args:
        events: Every event of the fork.
        lineage: The fork's own lineage.

    Returns:
        True when the events after the ``run_forked`` event hash to ``lineage.prefix_sha256``.
    """

    inherited = sorted(
        (event for event in events if lineage.seq < event.seq <= lineage.seq + lineage.inherited_events),
        key=lambda event: event.seq,
    )
    return len(inherited) == lineage.inherited_events and prefix_digest(inherited) == lineage.prefix_sha256


def build_history(events: Sequence[EventRecord]) -> RunHistory:
    """List the steps of one recorded run and whether each one can be forked.

    Args:
        events: Every event of one run, in any order.

    Returns:
        The run's history.

    Raises:
        ForkError: If there are no events or they belong to several runs.
    """

    return _scan(events).history


def reconstruct_fork_point(events: Sequence[EventRecord], step: int) -> ForkPoint:
    """Rebuild the runtime state after ``step`` of a recorded run.

    Args:
        events: Every event of one run, in any order.
        step: Steps completed (``0`` is the start).

    Returns:
        The reconstructed state and the events a fork inherits.

    Raises:
        ForkError: If the step was not recorded, ended the run, or never finished.
    """

    return _scan(events).fork_point(step)


def plan_fork(
    event_log: SQLiteEventLog,
    source_run_id: str,
    at_step: int,
    new_run_id: str,
    *,
    provider: str,
    policy: SafetyPolicy,
    bots: Mapping[str, BotSpec] | None = None,
    goal: str | None = None,
    bot_id: str | None = None,
) -> ForkPlan:
    """Validate a fork and compute what it will write and run, without writing anything.

    Safety checks, all fail-closed:

    * ``at_step`` must be a step whose resulting state was recorded: not beyond the source's
      last step, not the step that ended it, and not a step it was interrupted in.
    * ``new_run_id`` must not exist in the event log.
    * The bot active at the fork point and ``bot_id`` must be registered in ``bots``. Their tool
      scope comes from the registry, never from the event log, and must stay inside
      ``policy.allowed_tools``: a fork never widens the allowlist.
    * Switching bots is recorded as a handoff, so the fork's first decision is a model call
      under the new scope. A tool request the model made under the old scope is not executed.
    * ``policy.max_steps`` is the fork's whole budget; it must leave at least one step after
      ``at_step``. The goal passes ``policy.validate_goal``.

    Args:
        event_log: Event log holding the source run; the fork is written to the same log.
        source_run_id: Run to branch from.
        at_step: Step to branch after (``0`` starts over from the goal).
        new_run_id: Run id of the fork.
        provider: Provider name the fork continues with.
        policy: Safety policy of the fork: its allowlist before any bot scope, and its step budget.
        bots: Registered bots.
        goal: New goal, or ``None`` to keep the source's goal.
        bot_id: Bot to continue as, or ``None`` to keep the bot active at the fork point.

    Returns:
        The fork plan.

    Raises:
        ForkError: If any check fails.
    """

    if isinstance(at_step, bool) or not isinstance(at_step, int) or at_step < 0:
        raise ForkError(f"--at-step must be a step number >= 0, got {at_step!r}")
    if not new_run_id.strip():
        raise ForkError("--new-run-id must be non-empty")
    events = event_log.list_events(source_run_id)
    if not events:
        raise ForkError(f"run {source_run_id} not found in event log {event_log.path}")
    if event_log.list_events(new_run_id):
        raise ForkError(f"run {new_run_id} already exists in event log {event_log.path}; choose a new --new-run-id")
    scan = _scan(events)
    point = scan.fork_point(at_step)
    registry = dict(bots or {})

    source_bot = point.bot
    if source_bot is not None and source_bot not in registry:
        raise ForkError(
            f"step {at_step} of run {source_run_id} ran as bot {source_bot}, which is not registered; "
            "register it (CLI: --bots PATH) to fork this run"
        )
    if bot_id is not None and bot_id not in registry:
        known = ", ".join(sorted(registry)) or "none"
        raise ForkError(f"bot {bot_id} is not registered (registered bots: {known})")
    bot = bot_id if bot_id is not None else source_bot
    allowed_tools = policy.allowed_tools if bot is None else registry[bot].allowed_tools
    outside = sorted(allowed_tools - policy.allowed_tools)
    if outside:
        raise ForkError(
            f"bot {bot} allows tools outside the safety policy allowlist ({', '.join(outside)}); "
            "a fork never widens the allowlist"
        )
    if policy.max_steps <= at_step:
        raise ForkError(
            f"max_steps={policy.max_steps} leaves no step after step {at_step}; "
            f"use --max-steps {at_step + 1} or more (the budget counts inherited steps)"
        )
    effective_goal = point.goal if goal is None else goal
    try:
        policy.validate_goal(effective_goal)
    except SafetyError as error:
        raise ForkError(f"goal rejected: {error}") from error
    goal_changed = effective_goal != point.goal

    observations = point.observations
    if goal_changed and at_step == 0:
        observations = (Observation(source="user", content=effective_goal),)
    handoff: dict[str, Any] | None = None
    if bot != source_bot and bot is not None:
        summary = f"forked from {source_run_id} after step {at_step}"
        handoff = {
            "kind": "handoff",
            "fork_override": True,
            "from_bot": source_bot,
            "to_bot": bot,
            "summary": summary,
            "allowed_tools": sorted(allowed_tools),
        }
        observations = (
            *observations,
            Observation(
                source=f"handoff:{bot}",
                content=f"HANDED_OFF:{bot}:{summary}",
                metadata={"from_bot": source_bot, "to_bot": bot, "summary": summary},
            ),
        )
    if goal_changed and at_step > 0:
        observations = (
            *observations,
            Observation(
                source="user",
                content=effective_goal,
                metadata={"forked_from": source_run_id, "fork_step": at_step},
            ),
        )

    overrides: dict[str, Any] = {}
    if goal_changed:
        overrides["goal"] = effective_goal
    if bot != source_bot:
        overrides["bot"] = bot
    if provider != scan.history.provider:
        overrides["provider"] = provider
    lineage = {
        "parent_run_id": source_run_id,
        "fork_step": at_step,
        "parent_event": {
            "seq": point.event.seq,
            "event_type": point.event.event_type,
            "sha256": event_digest(point.event),
        },
        "inherited_events": len(point.prefix),
        "prefix_sha256": prefix_digest(point.prefix),
        "goal": effective_goal,
        "provider": provider,
        "bot": bot,
        "max_steps": policy.max_steps,
        "overrides": overrides,
    }
    engine = DeterministicDecisionEngine(provider_name=provider, bots=registry or None)
    next_decision = engine.decide(observations, at_step, replace(policy, allowed_tools=allowed_tools))
    return ForkPlan(
        source_run_id=source_run_id,
        new_run_id=new_run_id,
        point=point,
        goal=effective_goal,
        provider=provider,
        bot=bot,
        source_bot=source_bot,
        allowed_tools=allowed_tools,
        max_steps=policy.max_steps,
        observations=observations,
        handoff=handoff,
        lineage=lineage,
        next_decision=next_decision,
    )


@dataclass
class _PendingStep:
    """A decision whose step has not been closed by a checkpoint or terminal event yet."""

    bot: str | None
    action: str | None
    target: str | None
    rule_id: str | None
    outcome: str = "no result"


@dataclass(frozen=True)
class _Scan:
    """One pass over a run's events: its history plus what is needed to rebuild fork points."""

    events: tuple[EventRecord, ...]
    history: RunHistory
    checkpoints: Mapping[int, int]
    start_index: int | None
    start_bot: str | None

    def fork_point(self, step: int) -> ForkPoint:
        """Rebuild the state after ``step``, or explain why it cannot be forked."""

        history = self.history
        run_id = history.run_id
        forkable = ", ".join(str(item) for item in history.forkable_steps()) or "none"
        if step > history.last_step:
            raise ForkError(
                f"step {step} is beyond the last step of run {run_id} (step {history.last_step}); "
                f"forkable steps: {forkable}"
            )
        record = next((item for item in history.steps if item.step == step), None)
        if record is None or not record.forkable:
            if record is not None and record.outcome in _TERMINAL_STATES.values():
                reason = f"step {step} ended run {run_id} ({record.action} -> {record.outcome})"
            else:
                reason = f"step {step} of run {run_id} never recorded a result (the run was interrupted during it)"
            raise ForkError(f"{reason}; forkable steps: {forkable}")
        if step not in self.checkpoints:
            return self._start_point()
        index = self.checkpoints[step]
        event = self.events[index]
        try:
            snapshot = snapshot_from_event(event)
        except ValueError as error:
            raise ForkError(str(error)) from error
        if not snapshot.goal.strip() or not snapshot.observations:
            raise ForkError(f"checkpoint event {event.seq} of run {run_id} has no goal or observations")
        return ForkPoint(
            run_id=run_id,
            step=step,
            goal=snapshot.goal,
            observations=snapshot.observations,
            bot=snapshot.active_bot_id,
            event=event,
            prefix=self._prefix(index),
        )

    def _start_point(self) -> ForkPoint:
        """Rebuild the state a run without a step-0 checkpoint starts with: its first ``run_created`` goal."""

        if self.start_index is None:
            raise ForkError(f"run {self.history.run_id} has no run_created event, so step 0 cannot be rebuilt")
        event = self.events[self.start_index]
        goal = str(event.payload.get("goal", ""))
        if not goal.strip():
            raise ForkError(f"run_created event {event.seq} of run {self.history.run_id} has no goal")
        observation = Observation(source="user", content=goal)
        for candidate in self.events[self.start_index + 1 :]:
            if candidate.event_type == EventType.OBSERVATION.value:
                if candidate.payload.get("source") == "user" and candidate.payload.get("content") == goal:
                    observation = observation_from_dict(candidate.payload)
                break
        return ForkPoint(
            run_id=self.history.run_id,
            step=0,
            goal=goal,
            observations=(observation,),
            bot=self.start_bot,
            event=event,
            prefix=self._prefix(self.start_index),
        )

    def _prefix(self, cut: int) -> tuple[EventRecord, ...]:
        """Return the events up to ``cut``, without leading ``run_forked`` events cut off from their copies."""

        start = 0
        while start < cut and self.events[start].event_type == RUN_FORKED:
            inherited = _count(self.events[start].payload.get("inherited_events"))
            if inherited is not None and start + inherited <= cut:
                break
            start += 1
        prefix = self.events[start : cut + 1]
        for event in prefix:
            if event.event_type not in _EVENT_TYPES or event.state not in _RUN_STATES:
                raise ForkError(
                    f"event {event.seq} of run {event.run_id} has an unknown type or state "
                    f"({event.event_type}/{event.state}); it cannot be copied into a fork"
                )
        return prefix


def _scan(events: Sequence[EventRecord]) -> _Scan:
    """Walk a run's events once and collect its steps and fork points."""

    if not events:
        raise ForkError("no events to read")
    ordered = tuple(sorted(events, key=lambda event: event.seq))
    run_ids = {event.run_id for event in ordered}
    if len(run_ids) != 1:
        raise ForkError(f"events must belong to one run, got {len(run_ids)}")
    run_id = ordered[0].run_id
    lineage = parse_lineage(ordered[0])
    start_index = next(
        (index for index, event in enumerate(ordered) if event.event_type == EventType.RUN_CREATED.value), None
    )
    initial_bot = _initial_bot(ordered)
    used_names = _used_names(ordered, initial_bot)

    steps: dict[int, HistoryStep] = {}
    checkpoints: dict[int, int] = {}
    active_bot = initial_bot
    pending: _PendingStep | None = None
    last_closed = 0
    final_state = "unfinished"
    goal: str | None = None
    provider: str | None = None
    for index, event in enumerate(ordered):
        payload = event.payload
        kind = event.event_type
        if kind == EventType.RUN_CREATED.value and index == start_index:
            goal = _optional_str(payload.get("goal"))
            provider = _optional_str(payload.get("provider"))
            start = _PendingStep(bot=initial_bot, action=None, target=None, rule_id=None, outcome="start")
            steps[0] = _history_step(0, start, forkable=True, lineage=lineage, event_seq=event.seq)
        elif kind == EventType.DECISION.value:
            rationale = payload.get("rationale")
            pending = _PendingStep(
                bot=active_bot,
                action=_optional_str(payload.get("action")),
                target=_optional_str(payload.get("target")),
                rule_id=_optional_str(rationale.get("rule_id")) if isinstance(rationale, dict) else None,
            )
        elif kind == EventType.ACTION_RESULT.value:
            if payload.get("kind") == "handoff":
                active_bot = _optional_str(payload.get("to_bot"))
            if pending is not None:
                pending.outcome = _outcome(payload, used_names)
        elif kind == EventType.CHECKPOINT.value:
            step = _count(payload.get("step"))
            if step is None:
                continue
            active_bot = _optional_str(payload.get("active_bot_id"))
            checkpoints[step] = index
            if pending is None and step in steps:
                # A checkpoint with no new decision (a fork's starting state) replaces the state after that step.
                steps[step] = replace(steps[step], forkable=True, event_seq=event.seq)
            else:
                closed = pending or _PendingStep(bot=None, action=None, target=None, rule_id=None, outcome="checkpoint")
                steps[step] = _history_step(step, closed, forkable=True, lineage=lineage, event_seq=event.seq)
            last_closed = step
            pending = None
        elif kind in _TERMINAL_STATES:
            final_state = _TERMINAL_STATES[kind]
            if pending is not None:
                pending.outcome = final_state
                steps[last_closed + 1] = _history_step(
                    last_closed + 1, pending, forkable=False, lineage=lineage, event_seq=None
                )
                pending = None
    if pending is not None:
        pending.outcome = "interrupted"
        step = last_closed + 1
        steps[step] = _history_step(step, pending, forkable=False, lineage=lineage, event_seq=None)

    if lineage is not None:
        goal = lineage.goal or goal
        provider = lineage.provider or provider
    history = RunHistory(
        run_id=run_id,
        goal=goal,
        provider=provider,
        final_state=final_state,
        steps=tuple(steps[number] for number in sorted(steps)),
        lineage=lineage,
    )
    return _Scan(
        events=ordered,
        history=history,
        checkpoints=checkpoints,
        start_index=start_index,
        start_bot=initial_bot,
    )


def _history_step(
    step: int,
    pending: _PendingStep,
    *,
    forkable: bool,
    lineage: ForkLineage | None,
    event_seq: int | None,
) -> HistoryStep:
    """Close a pending step."""

    return HistoryStep(
        step=step,
        bot=pending.bot,
        action=pending.action,
        target=pending.target,
        rule_id=pending.rule_id,
        outcome=pending.outcome,
        forkable=forkable,
        inherited=lineage is not None and step <= lineage.fork_step,
        event_seq=event_seq,
    )


def _outcome(payload: Mapping[str, Any], used_names: Mapping[str, frozenset[str]]) -> str:
    """Summarize an ``action_result`` payload in a few words.

    A ``TOOL:``/``HANDOFF:`` target is whatever the model wrote before the next colon, so it is
    shown only when it names a tool the run called or a bot it ran (as in Mermaid exports).
    """

    kind = payload.get("kind")
    if kind == "llm":
        output = str(payload.get("output", ""))
        for directive in _DIRECTIVES:
            if output.startswith(f"{directive}:"):
                target = output.split(":", 2)[1].strip() if directive != "DONE" else ""
                return f"{directive} {target}" if target in used_names.get(directive, frozenset()) else directive
        return "reply"
    if kind == "tool":
        return f"{payload.get('tool')} {'ok' if payload.get('ok') else 'error'}"
    if kind == "handoff":
        return f"handoff to {payload.get('to_bot')}"
    return str(kind)


def _used_names(events: Sequence[EventRecord], initial_bot: str | None) -> dict[str, frozenset[str]]:
    """Return the tools a run called and the bots it ran, keyed by the directive that names them."""

    tools: list[Any] = []
    bots: list[Any] = [initial_bot]
    for event in events:
        payload = event.payload
        if event.event_type == EventType.DECISION.value and payload.get("action") == "call_tool":
            tools.append(payload.get("target"))
        elif event.event_type == EventType.ACTION_RESULT.value and payload.get("kind") == "tool":
            tools.append(payload.get("tool"))
        elif event.event_type == EventType.ACTION_RESULT.value and payload.get("kind") == "handoff":
            bots.append(payload.get("to_bot"))
        elif event.event_type == EventType.CHECKPOINT.value:
            bots.append(payload.get("active_bot_id"))
    return {
        "TOOL": frozenset(name for name in map(_optional_str, tools) if name is not None),
        "HANDOFF": frozenset(name for name in map(_optional_str, bots) if name is not None),
    }


def _initial_bot(events: Sequence[EventRecord]) -> str | None:
    """Return the bot active when the run started, from its first handoff or bot checkpoint."""

    for event in events:
        if event.event_type == EventType.ACTION_RESULT.value and event.payload.get("kind") == "handoff":
            return _optional_str(event.payload.get("from_bot"))
        if event.event_type == EventType.CHECKPOINT.value:
            active = _optional_str(event.payload.get("active_bot_id"))
            if active is not None:
                return active
    return None


def _count(value: Any) -> int | None:
    """Return a non-negative integer, or ``None`` for anything else (including booleans)."""

    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _optional_str(value: Any) -> str | None:
    """Return a non-empty string or ``None``."""

    return value if isinstance(value, str) and value else None
