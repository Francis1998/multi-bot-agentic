"""Parse one run's durable event records into an ordered, typed timeline.

The timeline is the shared input of the OpenTelemetry span builder and the Mermaid renderer.
It pairs every decision with its ``action_requested``/``action_result`` events, tracks which
bot was active, and records handoffs, approvals, checkpoints, resumes, fork points, and the outcome.
Parsing is pure: it never calls a provider or a tool and never touches the event log.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Final, TypeAlias, TypeGuard

from multi_bot_agentic.event_log import EventRecord

# Terminal event types and the run state each one records.
TERMINAL_EVENT_STATES: Mapping[str, str] = {
    "run_completed": "succeeded",
    "run_failed": "failed",
    "run_cancelled": "cancelled",
}

_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
# Rule id of the handoff a fork records when it switches bots (mirrors multi_bot_agentic.fork).
FORK_BOT_OVERRIDE_RULE: Final[str] = "fork.bot-override"


class TraceInputError(ValueError):
    """Raised when event records cannot be turned into a trace."""


@dataclass(frozen=True)
class DecisionRef:
    """A recorded decision and its rationale trace.

    Attributes:
        seq: Sequence number of the ``decision`` event.
        timestamp: Event timestamp (ISO 8601).
        action: Selected action (``call_llm``, ``call_tool``, ``handoff``, ``finish``, ...).
        target: Provider, tool, or bot the action targets.
        rule_id: Rule that selected the action.
        explanation: Engine-generated explanation of the rule.
        rejected_actions: Candidate actions the engine rejected.
        observations_used: Observation ids the rule used.
        payload: Action payload (tool arguments, handoff summary, answer); may hold user content.
    """

    seq: int
    timestamp: str
    action: str
    target: str | None
    rule_id: str
    explanation: str
    rejected_actions: tuple[str, ...]
    observations_used: tuple[str, ...]
    payload: Mapping[str, Any]


@dataclass(frozen=True)
class ObservationRef:
    """One observation the runner recorded before a decision.

    Attributes:
        source: Observation source (``user``, ``llm:<provider>``, ``tool:<name>``, ``handoff:<bot>``).
        content: Observation text (user or model content).
    """

    source: str
    content: str


@dataclass(frozen=True)
class ModelCall:
    """A ``call_llm`` action.

    Attributes:
        decision: Decision that requested the call.
        requested_seq: Sequence number of the ``action_requested`` event.
        started_at: Timestamp of the ``action_requested`` event.
        ended_at: Timestamp of the ``action_result`` event, or of the closest event that ended the call.
        agent: Bot active during the call, if known.
        provider: Provider adapter name.
        inputs: Observations recorded for the step that made the call.
        output: Model output text, or ``None`` when no result was recorded.
        metadata: Non-secret provider metadata recorded with the output.
        failure: Failure reason when the call never produced a result.
        interrupted: True when the run was resumed before the call recorded a result.
    """

    decision: DecisionRef
    requested_seq: int
    started_at: str
    ended_at: str
    agent: str | None
    provider: str
    inputs: tuple[ObservationRef, ...]
    output: str | None
    metadata: Mapping[str, Any]
    failure: str | None = None
    interrupted: bool = False


@dataclass(frozen=True)
class ToolCall:
    """A ``call_tool`` action (built-in or MCP tool).

    Attributes:
        decision: Decision that requested the call.
        requested_seq: Sequence number of the ``action_requested`` event.
        started_at: Timestamp of the ``action_requested`` event.
        ended_at: Timestamp of the ``action_result`` event, or of the closest event that ended the call.
        agent: Bot active during the call, if known.
        tool: Registered tool name.
        ok: Tool success flag, or ``None`` when no result was recorded.
        content: Tool result text, or ``None`` when no result was recorded.
        metadata: Tool result metadata (MCP server, era, error kind, ...).
        failure: Failure reason when the call never produced a result.
        interrupted: True when the run was resumed before the call recorded a result.
    """

    decision: DecisionRef
    requested_seq: int
    started_at: str
    ended_at: str
    agent: str | None
    tool: str
    ok: bool | None
    content: str | None
    metadata: Mapping[str, Any]
    failure: str | None = None
    interrupted: bool = False


@dataclass(frozen=True)
class Handoff:
    """A bot handoff decided by ``HANDOFF:<bot>:<summary>``.

    Attributes:
        decision: Handoff decision.
        seq: Sequence number of the handoff result (or of the decision when it never completed).
        at: Timestamp of that event.
        from_bot: Bot that handed off, if known.
        to_bot: Target bot.
        summary: Handoff summary written by the model (content).
        allowed_tools: Tool scope of the target bot.
        completed: False when the runner rejected the handoff before switching bots.
    """

    decision: DecisionRef
    seq: int
    at: str
    from_bot: str | None
    to_bot: str
    summary: str
    allowed_tools: tuple[str, ...]
    completed: bool = True


@dataclass(frozen=True)
class Approval:
    """A human-in-the-loop approval recorded as ``action_result`` with ``kind: approval``.

    Attributes:
        seq: Sequence number of the approval event.
        at: Event timestamp.
        agent: Bot active when the approval was recorded, if known.
        tool: Tool that required approval.
        status: ``pending``, ``approved``, or ``rejected``.
        request_id: Approval request id, if recorded.
    """

    seq: int
    at: str
    agent: str | None
    tool: str
    status: str
    request_id: str | None


@dataclass(frozen=True)
class FinalDecision:
    """A ``finish``, ``fail``, or ``cancel`` decision that ends the run.

    Attributes:
        decision: The terminal decision.
    """

    decision: DecisionRef


@dataclass(frozen=True)
class Checkpoint:
    """A resumable checkpoint.

    Attributes:
        seq: Sequence number of the checkpoint event.
        at: Event timestamp.
        step: Next zero-based step a resume would execute.
        active_bot_id: Bot whose scope the checkpoint restores, if any.
    """

    seq: int
    at: str
    step: int | None
    active_bot_id: str | None


@dataclass(frozen=True)
class Resume:
    """A ``resume`` that continued the run from its latest checkpoint.

    Attributes:
        seq: Sequence number of the resumed run's first state transition.
        at: Event timestamp.
    """

    seq: int
    at: str


@dataclass(frozen=True)
class Fork:
    """A fork point: where events copied from a parent run end and the fork's own steps begin.

    A fork's own ``run_forked`` event is its first event. An ancestor's ``run_forked`` event can
    also appear among the copied events, when the parent was itself a fork.

    Attributes:
        seq: Sequence number of the last copied event (the fork's own steps start after it).
        at: Timestamp of that event.
        parent_run_id: Run the fork branched from.
        fork_step: Steps of the parent that were copied.
        inherited_events: Number of copied events.
        overrides: Names of the settings the fork changed (``goal``, ``bot``, ``provider``).
        own: True for this run's own fork point, False for an ancestor's.
    """

    seq: int
    at: str
    parent_run_id: str
    fork_step: int
    inherited_events: int
    overrides: tuple[str, ...]
    own: bool


Step: TypeAlias = ModelCall | ToolCall | Handoff | Approval | FinalDecision | Checkpoint | Resume | Fork


@dataclass(frozen=True)
class Outcome:
    """The run's terminal event.

    Attributes:
        seq: Sequence number of the terminal event.
        at: Event timestamp.
        state: ``succeeded``, ``failed``, or ``cancelled``.
        answer: Final answer (content) for succeeded runs.
        reason: Failure or cancellation reason.
        steps: Loop steps the run took.
    """

    seq: int
    at: str
    state: str
    answer: str | None
    reason: str | None
    steps: int | None


@dataclass(frozen=True)
class RunTimeline:
    """Typed view of one run's events.

    Attributes:
        run_id: Run identifier.
        goal: User goal (content), if recorded.
        provider: Provider adapter name, if recorded.
        started_at: Timestamp of the run's first event.
        ended_at: Timestamp of the run's last event.
        first_seq: Sequence number of the first event.
        event_count: Number of events.
        initial_bot: Bot active when the run started, if known.
        steps: Ordered actions, handoffs, approvals, terminal decisions, checkpoints, resumes, and
            fork points.
        outcome: Terminal event, or ``None`` for an unfinished run.
        final_decision: Last ``finish``/``fail``/``cancel`` decision, if any.
        fork: Where this run was forked from, or ``None`` for an original run.
        inherited_through_seq: Sequence number of the last event copied from the parent (0 if not a fork).
    """

    run_id: str
    goal: str | None
    provider: str | None
    started_at: str
    ended_at: str
    first_seq: int
    event_count: int
    initial_bot: str | None
    steps: tuple[Step, ...]
    outcome: Outcome | None
    final_decision: DecisionRef | None
    fork: Fork | None = None
    inherited_through_seq: int = 0

    @property
    def final_state(self) -> str:
        """Return the terminal state, or ``unfinished`` when the run has no terminal event."""

        return self.outcome.state if self.outcome is not None else "unfinished"


def timestamp_to_unix_nanos(value: str) -> int:
    """Convert an event-log timestamp into nanoseconds since the Unix epoch.

    Integer arithmetic keeps the conversion exact. Timestamps without an offset are UTC.

    Args:
        value: ISO 8601 timestamp such as ``2026-11-07T18:06:47.710045+00:00``.

    Returns:
        Nanoseconds since 1970-01-01T00:00:00Z.

    Raises:
        TraceInputError: If the timestamp is not ISO 8601.
    """

    text = value.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as error:
        raise TraceInputError(f"invalid event timestamp: {value!r}") from error
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    delta = parsed - _EPOCH
    return (delta.days * 86_400 + delta.seconds) * 1_000_000_000 + delta.microseconds * 1_000


def select_latest_run(last_event_timestamps: Mapping[str, str]) -> str | None:
    """Pick the most recently active run.

    Args:
        last_event_timestamps: Each run's latest event timestamp, keyed by run id.

    Returns:
        The run whose latest event is newest (ties go to the greatest run id), or ``None``.
    """

    if not last_event_timestamps:
        return None
    return max(
        last_event_timestamps, key=lambda run_id: (timestamp_to_unix_nanos(last_event_timestamps[run_id]), run_id)
    )


def parse_run(events: Sequence[EventRecord]) -> RunTimeline:
    """Build the typed timeline of one run.

    Args:
        events: Every event of exactly one run, in any order.

    Returns:
        The run's timeline.

    Raises:
        TraceInputError: If there are no events, events from several runs, or invalid timestamps.
    """

    if not events:
        raise TraceInputError("no events to trace")
    run_ids = sorted({event.run_id for event in events})
    if len(run_ids) != 1:
        raise TraceInputError(f"events must belong to one run, got {len(run_ids)}: {', '.join(run_ids[:5])}")
    ordered = sorted(events, key=lambda event: event.seq)
    for event in ordered:
        try:
            timestamp_to_unix_nanos(event.timestamp)
        except TraceInputError as error:
            raise TraceInputError(f"event {event.seq} of run {event.run_id}: {error}") from error
    return _TimelineBuilder(ordered).build()


@dataclass
class _OpenAction:
    """A requested action still waiting for its result."""

    decision: DecisionRef
    requested: EventRecord
    agent: str | None
    inputs: tuple[ObservationRef, ...]
    next_at: str | None = None


@dataclass
class _TimelineBuilder:
    """Single pass over ordered events that assembles a :class:`RunTimeline`."""

    events: Sequence[EventRecord]
    steps: list[Step] = field(default_factory=list)
    goal: str | None = None
    provider: str | None = None
    active_bot: str | None = None
    observations: list[ObservationRef] = field(default_factory=list)
    pending_decision: DecisionRef | None = None
    pending_handoff: DecisionRef | None = None
    open_action: _OpenAction | None = None
    seen_checkpoint: bool = False
    outcome: Outcome | None = None
    final_decision: DecisionRef | None = None
    fork_starting: bool = False

    def build(self) -> RunTimeline:
        """Consume every event and return the timeline."""

        initial_bot = _initial_bot(self.events)
        self.active_bot = initial_bot
        fork_points = _fork_points(self.events)
        for event in self.events:
            open_action = self.open_action
            if open_action is not None and open_action.requested is not event and open_action.next_at is None:
                open_action.next_at = event.timestamp
            self._consume(event)
            forks = fork_points.get(event.seq, [])
            self.steps.extend(forks)
            if forks:
                self.fork_starting = True
        if self.open_action is not None:
            self._close_open_action(ended_at=self.open_action.requested.timestamp, failure=None, interrupted=False)
        first, last = self.events[0], self.events[-1]
        own = next((fork for forks in fork_points.values() for fork in forks if fork.own), None)
        lineage = first.payload if own is not None else {}
        return RunTimeline(
            run_id=first.run_id,
            goal=_optional_str(lineage.get("goal")) or self.goal,
            provider=_optional_str(lineage.get("provider")) or self.provider,
            started_at=first.timestamp,
            ended_at=last.timestamp,
            first_seq=first.seq,
            event_count=len(self.events),
            initial_bot=initial_bot,
            steps=tuple(self.steps),
            outcome=self.outcome,
            final_decision=self.final_decision,
            fork=own,
            inherited_through_seq=own.seq if own is not None else 0,
        )

    def _consume(self, event: EventRecord) -> None:
        """Dispatch one event by type."""

        payload = event.payload
        if event.event_type == "run_created":
            self.goal = _optional_str(payload.get("goal")) or self.goal
            self.provider = _optional_str(payload.get("provider")) or self.provider
        elif event.event_type == "state_transition":
            self._on_transition(event)
        elif event.event_type == "observation":
            self.observations.append(
                ObservationRef(source=str(payload.get("source", "")), content=str(payload.get("content", "")))
            )
        elif event.event_type == "decision":
            self._on_decision(_decision_ref(event))
        elif event.event_type == "action_requested":
            self._on_action_requested(event)
        elif event.event_type == "action_result":
            self._on_action_result(event)
        elif event.event_type == "checkpoint":
            self.seen_checkpoint = True
            if self.goal is None:
                self.goal = _optional_str(payload.get("goal"))
            step = payload.get("step")
            self.steps.append(
                Checkpoint(
                    seq=event.seq,
                    at=event.timestamp,
                    step=step if isinstance(step, int) and not isinstance(step, bool) else None,
                    active_bot_id=_optional_str(payload.get("active_bot_id")),
                )
            )
        elif event.event_type in TERMINAL_EVENT_STATES:
            self._on_terminal(event)

    def _on_transition(self, event: EventRecord) -> None:
        """Track step boundaries and detect resumes (a fresh state machine after a checkpoint).

        The first fresh state machine after a fork point starts the fork's own steps, not a resume.
        """

        if event.payload.get("to") != "observing":
            return
        self.observations = []
        if event.payload.get("from") == "created" and self.fork_starting:
            self.fork_starting = False
        elif event.payload.get("from") == "created" and self.seen_checkpoint:
            if self.open_action is not None:
                self._close_open_action(
                    ended_at=self.open_action.requested.timestamp,
                    failure="interrupted before a result was recorded",
                    interrupted=True,
                )
            self.pending_handoff = None
            self.steps.append(Resume(seq=event.seq, at=event.timestamp))

    def _on_decision(self, decision: DecisionRef) -> None:
        """Record terminal decisions and remember pending ones."""

        if decision.action in {"finish", "fail", "cancel"}:
            self.final_decision = decision
            self.steps.append(FinalDecision(decision=decision))
        elif decision.action == "handoff":
            self.pending_handoff = decision
        else:
            self.pending_decision = decision
        if self.provider is None and decision.action == "call_llm" and decision.target:
            self.provider = decision.target

    def _on_action_requested(self, event: EventRecord) -> None:
        """Open a model or tool action."""

        decision = _decision_ref(event)
        pending = self.pending_decision
        if pending is not None and pending.action == decision.action and pending.target == decision.target:
            decision = pending
        self.pending_decision = None
        if decision.action not in {"call_llm", "call_tool"}:
            return
        self.open_action = _OpenAction(
            decision=decision,
            requested=event,
            agent=self.active_bot,
            inputs=tuple(self.observations),
        )

    def _on_action_result(self, event: EventRecord) -> None:
        """Close the matching action, or record a handoff or approval."""

        payload = event.payload
        kind = payload.get("kind")
        open_action = self.open_action
        if kind == "llm" and open_action is not None and open_action.decision.action == "call_llm":
            self.open_action = None
            self.steps.append(
                ModelCall(
                    decision=open_action.decision,
                    requested_seq=open_action.requested.seq,
                    started_at=open_action.requested.timestamp,
                    ended_at=event.timestamp,
                    agent=open_action.agent,
                    provider=open_action.decision.target or self.provider or "unknown",
                    inputs=open_action.inputs,
                    output=str(payload.get("output", "")),
                    metadata=_mapping(payload.get("metadata")),
                )
            )
        elif kind == "tool" and open_action is not None and open_action.decision.action == "call_tool":
            self.open_action = None
            self.steps.append(
                ToolCall(
                    decision=open_action.decision,
                    requested_seq=open_action.requested.seq,
                    started_at=open_action.requested.timestamp,
                    ended_at=event.timestamp,
                    agent=open_action.agent,
                    tool=str(payload.get("tool") or open_action.decision.target or "unknown"),
                    ok=bool(payload.get("ok")),
                    content=str(payload.get("content", "")),
                    metadata=_mapping(payload.get("metadata")),
                )
            )
        elif kind == "handoff":
            self._on_handoff(event)
        elif kind == "approval":
            self.steps.append(
                Approval(
                    seq=event.seq,
                    at=event.timestamp,
                    agent=self.active_bot,
                    tool=str(payload.get("tool") or "unknown"),
                    status=str(payload.get("status") or "unknown"),
                    request_id=_optional_str(payload.get("request_id")),
                )
            )

    def _on_handoff(self, event: EventRecord) -> None:
        """Record a completed handoff and switch the active bot."""

        payload = event.payload
        to_bot = _optional_str(payload.get("to_bot")) or "unknown"
        rule_id = FORK_BOT_OVERRIDE_RULE if payload.get("fork_override") is True else ""
        decision = self.pending_handoff or _synthetic_decision(event, action="handoff", target=to_bot, rule_id=rule_id)
        self.pending_handoff = None
        allowed = payload.get("allowed_tools")
        self.steps.append(
            Handoff(
                decision=decision,
                seq=event.seq,
                at=event.timestamp,
                from_bot=_optional_str(payload.get("from_bot")),
                to_bot=to_bot,
                summary=str(payload.get("summary", "")),
                allowed_tools=tuple(str(item) for item in allowed) if isinstance(allowed, list) else (),
            )
        )
        self.active_bot = to_bot

    def _on_terminal(self, event: EventRecord) -> None:
        """Record the outcome and close anything the failure interrupted."""

        payload = event.payload
        state = TERMINAL_EVENT_STATES[event.event_type]
        reason = _optional_str(payload.get("reason"))
        if self.open_action is not None:
            ended_at = self.open_action.next_at or event.timestamp
            self._close_open_action(ended_at=ended_at, failure=reason or state, interrupted=False)
        if self.pending_handoff is not None:
            decision = self.pending_handoff
            self.pending_handoff = None
            self.steps.append(
                Handoff(
                    decision=decision,
                    seq=decision.seq,
                    at=decision.timestamp,
                    from_bot=self.active_bot,
                    to_bot=decision.target or "unknown",
                    summary=str(decision.payload.get("summary", "")),
                    allowed_tools=(),
                    completed=False,
                )
            )
        steps = payload.get("steps")
        self.outcome = Outcome(
            seq=event.seq,
            at=event.timestamp,
            state=state,
            answer=_optional_str(payload.get("answer")) if state == "succeeded" else None,
            reason=reason,
            steps=steps if isinstance(steps, int) and not isinstance(steps, bool) else None,
        )

    def _close_open_action(self, *, ended_at: str, failure: str | None, interrupted: bool) -> None:
        """Turn the open action into a step that has no recorded result."""

        open_action = self.open_action
        if open_action is None:
            return
        self.open_action = None
        decision = open_action.decision
        if decision.action == "call_llm":
            self.steps.append(
                ModelCall(
                    decision=decision,
                    requested_seq=open_action.requested.seq,
                    started_at=open_action.requested.timestamp,
                    ended_at=ended_at,
                    agent=open_action.agent,
                    provider=decision.target or self.provider or "unknown",
                    inputs=open_action.inputs,
                    output=None,
                    metadata={},
                    failure=failure,
                    interrupted=interrupted,
                )
            )
        else:
            self.steps.append(
                ToolCall(
                    decision=decision,
                    requested_seq=open_action.requested.seq,
                    started_at=open_action.requested.timestamp,
                    ended_at=ended_at,
                    agent=open_action.agent,
                    tool=decision.target or "unknown",
                    ok=None,
                    content=None,
                    metadata={},
                    failure=failure,
                    interrupted=interrupted,
                )
            )


def _initial_bot(events: Sequence[EventRecord]) -> str | None:
    """Return the bot active when the run started, from its first handoff or checkpoint."""

    for event in events:
        if event.event_type == "action_result" and event.payload.get("kind") == "handoff":
            return _optional_str(event.payload.get("from_bot"))
        if event.event_type == "checkpoint":
            active = _optional_str(event.payload.get("active_bot_id"))
            if active is not None:
                return active
    return None


def _fork_points(events: Sequence[EventRecord]) -> dict[int, list[Fork]]:
    """Return the fork points of a run keyed by the sequence number of their last copied event.

    Every ``run_forked`` event (the run's own, and ancestors' among its copied events) is followed
    by ``inherited_events`` copied events, so its fork point is that many events after it. Fork
    points that share an event are listed oldest first: an ancestor's before the run's own.
    """

    points: dict[int, list[Fork]] = {}
    first_seq = events[0].seq
    timestamps = {event.seq: event.timestamp for event in events}
    for event in events:
        if event.event_type != "run_forked":
            continue
        payload = event.payload
        parent = _optional_str(payload.get("parent_run_id"))
        fork_step = payload.get("fork_step")
        inherited = payload.get("inherited_events")
        if parent is None or not _is_count(fork_step) or not _is_count(inherited):
            continue
        overrides = payload.get("overrides")
        boundary = event.seq + inherited
        fork = Fork(
            seq=boundary,
            at=timestamps.get(boundary, event.timestamp),
            parent_run_id=parent,
            fork_step=fork_step,
            inherited_events=inherited,
            overrides=tuple(sorted(str(key) for key in overrides)) if isinstance(overrides, dict) else (),
            own=event.seq == first_seq,
        )
        # A later run_forked event among the copies belongs to an older fork (an ancestor), so it goes first.
        points.setdefault(boundary, []).insert(0, fork)
    return points


def _is_count(value: Any) -> TypeGuard[int]:
    """Return whether ``value`` is a non-negative integer (booleans excluded)."""

    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _decision_ref(event: EventRecord) -> DecisionRef:
    """Build a decision reference from a ``decision`` or ``action_requested`` event."""

    payload = event.payload
    rationale = _mapping(payload.get("rationale"))
    return DecisionRef(
        seq=event.seq,
        timestamp=event.timestamp,
        action=str(payload.get("action", "")),
        target=_optional_str(payload.get("target")),
        rule_id=str(rationale.get("rule_id", "")),
        explanation=str(rationale.get("explanation", "")),
        rejected_actions=_strings(rationale.get("rejected_actions")),
        observations_used=_strings(rationale.get("observations_used")),
        payload=_mapping(payload.get("payload")),
    )


def _synthetic_decision(event: EventRecord, *, action: str, target: str | None, rule_id: str = "") -> DecisionRef:
    """Stand in for a decision event that is missing from the log (or, for fork bot overrides, never existed)."""

    return DecisionRef(
        seq=event.seq,
        timestamp=event.timestamp,
        action=action,
        target=target,
        rule_id=rule_id,
        explanation="",
        rejected_actions=(),
        observations_used=(),
        payload={},
    )


def _mapping(value: Any) -> Mapping[str, Any]:
    """Return ``value`` when it is a JSON object, otherwise an empty mapping."""

    return value if isinstance(value, dict) else {}


def _strings(value: Any) -> tuple[str, ...]:
    """Return the string items of a JSON array."""

    return tuple(str(item) for item in value) if isinstance(value, list) else ()


def _optional_str(value: Any) -> str | None:
    """Return a non-empty string or ``None``."""

    return value if isinstance(value, str) and value else None


def nanos_between(start: str, end: str) -> tuple[int, int]:
    """Return ``(start, end)`` in Unix nanoseconds, clamping ``end`` so it never precedes ``start``.

    Args:
        start: Start timestamp.
        end: End timestamp.

    Returns:
        Start and end nanoseconds.
    """

    start_nanos = timestamp_to_unix_nanos(start)
    return start_nanos, max(start_nanos, timestamp_to_unix_nanos(end))
