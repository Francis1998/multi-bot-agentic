"""Observe -> Decide -> Act runner."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any
from uuid import uuid4

from multi_bot_agentic.approval import (
    ApprovalDecision,
    ApprovalError,
    AwaitingApprovalError,
    InterruptRecord,
    collect_interrupts,
    find_interrupt,
    interrupt_payload,
    new_interrupt_id,
    rejection_observation,
)
from multi_bot_agentic.bots import BotSpec
from multi_bot_agentic.checkpoint import CheckpointSnapshot, load_latest_checkpoint, save_checkpoint
from multi_bot_agentic.decision import DeterministicDecisionEngine
from multi_bot_agentic.event_log import EventRecord, SQLiteEventLog
from multi_bot_agentic.fork import plan_fork
from multi_bot_agentic.lifecycle import InvalidTransitionError, RunStateMachine
from multi_bot_agentic.llm.base import LLMAdapter
from multi_bot_agentic.models import (
    Decision,
    EventType,
    ModelRequest,
    Observation,
    RationaleTrace,
    RunState,
    ToolInvocation,
    ToolResult,
    ToolSpec,
)
from multi_bot_agentic.safety import SafetyError, SafetyPolicy
from multi_bot_agentic.tools.base import ToolAdapter


@dataclass(frozen=True)
class RunResult:
    """Final run result.

    Attributes:
        run_id: Run identifier.
        state: Terminal lifecycle state.
        answer: Final answer, or the failure/cancellation reason.
        steps: Number of loop steps the run took.
        already_finished: True when ``resume`` found the run already finished and returned
            its recorded outcome without executing anything.
        interrupt: The interrupt the run paused at when ``state`` is ``awaiting_approval``.
    """

    run_id: str
    state: RunState
    answer: str
    steps: int
    already_finished: bool = False
    interrupt: InterruptRecord | None = None


class ResumeError(ValueError):
    """Raised when ``AgentRunner.resume`` cannot continue a run; nothing is executed or appended.

    It subclasses ``ValueError``, which ``resume`` raised before, so existing handlers keep working.
    """


class RunNotFoundError(ResumeError):
    """Raised when the event log holds no events for the run id to resume."""


class RunExistsError(ValueError):
    """Raised when ``AgentRunner.run`` gets a run id the event log already holds; nothing is appended."""


# Event types that end a run, mapped to the terminal state they record.
_TERMINAL_EVENT_STATES: dict[str, RunState] = {
    EventType.RUN_COMPLETED.value: RunState.SUCCEEDED,
    EventType.RUN_FAILED.value: RunState.FAILED,
    EventType.RUN_CANCELLED.value: RunState.CANCELLED,
}


def recorded_outcome(event_log: SQLiteEventLog, run_id: str) -> RunResult | None:
    """Return the recorded outcome of a run that already reached a terminal state.

    Terminal lifecycle states have no outgoing transitions; reading them from the durable
    log enforces that across processes, where a fresh state machine cannot. Needs only the
    event log, so callers can check before starting providers or MCP servers.

    Args:
        event_log: Durable event log.
        run_id: Run identifier.

    Returns:
        The outcome stored by the run's latest terminal event (``already_finished=True``),
        or ``None`` when the run has not finished.
    """

    terminal: EventRecord | None = None
    for event in event_log.list_events(run_id):
        if event.event_type in _TERMINAL_EVENT_STATES:
            terminal = event
    if terminal is None:
        return None
    state = _TERMINAL_EVENT_STATES[terminal.event_type]
    answer = terminal.payload.get("answer" if state is RunState.SUCCEEDED else "reason", "")
    steps = terminal.payload.get("steps")
    return RunResult(
        run_id=run_id,
        state=state,
        answer=str(answer),
        steps=steps if isinstance(steps, int) else 0,
        already_finished=True,
    )


class AgentRunner:
    """Runs an auditable Observe -> Decide -> Act loop."""

    def __init__(
        self,
        provider: LLMAdapter,
        event_log: SQLiteEventLog,
        tools: dict[str, ToolAdapter],
        safety_policy: SafetyPolicy,
        bots: dict[str, BotSpec] | None = None,
        active_bot_id: str | None = None,
        tool_specs: Sequence[ToolSpec] = (),
    ) -> None:
        """Initialize the runner.

        Args:
            provider: LLM provider adapter.
            event_log: Durable event log.
            tools: Registered tool adapters by name.
            safety_policy: Runtime safety controls.
            bots: Optional registered bots for typed handoffs.
            active_bot_id: Optional bot that is active when each run starts.
            tool_specs: Optional tool catalog advertised to the provider (for example MCP
                tools). Only specs for registered tools allowed by the live safety policy
                are sent, so bot handoffs also narrow what the model sees.
        """

        self.provider = provider
        self.event_log = event_log
        self.tools = tools
        self.safety_policy = safety_policy
        self.bots = dict(bots or {})
        self.active_bot_id = active_bot_id
        self.tool_specs = tuple(tool_specs)
        # The allowlist before any bot scope; forks never run with tools outside it.
        self._policy_allowed_tools = safety_policy.allowed_tools
        if self.active_bot_id is not None:
            if self.active_bot_id not in self.bots:
                raise ValueError(f"active_bot_id is not registered: {self.active_bot_id}")
            self.safety_policy = replace(
                self.safety_policy,
                allowed_tools=self.bots[self.active_bot_id].allowed_tools,
            )
        self._initial_bot_id = self.active_bot_id
        self._initial_allowed_tools = self.safety_policy.allowed_tools
        self._initial_require_approval = self.safety_policy.require_approval
        self.decision_engine = DeterministicDecisionEngine(
            provider_name=provider.provider_name,
            bots=self.bots or None,
        )

    def run(self, goal: str, run_id: str | None = None) -> RunResult:
        """Execute one bounded agent run.

        Every run starts with the constructor's ``active_bot_id`` and tool scope. A
        handoff lasts only for the run that made it, so a reused runner never starts a
        run with the scope an earlier ``run`` or ``resume`` left behind.

        Args:
            goal: User goal.
            run_id: Optional run identifier; one the event log already holds is refused, so a
                second run is never appended to a recorded one (``resume`` continues a run).

        Returns:
            Final run result.

        Raises:
            RunExistsError: If the event log already holds events for ``run_id``.
        """

        self.safety_policy.validate_goal(goal)
        if run_id and self.event_log.list_events(run_id):
            raise RunExistsError(
                f"run {run_id} already exists in event log {self.event_log.path}; "
                "choose a new run id (resume continues an interrupted run)"
            )
        self._restore_initial_scope()
        selected_run_id = run_id or str(uuid4())
        state_machine = RunStateMachine()
        observations: tuple[Observation, ...] = (Observation(source="user", content=goal),)
        created: dict[str, Any] = {"goal": goal, "provider": self.provider.provider_name}
        if self.safety_policy.require_approval:
            created["require_approval"] = sorted(self.safety_policy.require_approval)
        self.event_log.append(selected_run_id, state_machine.state, EventType.RUN_CREATED, created)
        return self._run_loop(selected_run_id, goal, observations, state_machine, start_step=0)

    def resume(self, run_id: str) -> RunResult:
        """Resume an interrupted run from its latest checkpoint.

        Only a run without a terminal event (``run_completed``, ``run_failed`` or
        ``run_cancelled``) is continued, for example after its process was killed. A
        finished run is never re-executed: its recorded outcome is returned with
        ``already_finished=True`` and no events are appended, so ``resume`` is idempotent.

        The bot that was active when the checkpoint was written is restored, so a
        resumed run keeps that bot's tool scope instead of the constructor's. A
        checkpoint without a bot resumes with the constructor's scope, never with one
        left behind by an earlier run on this runner. The approval policy recorded in the
        checkpoint stays in force (this runner's ``require_approval`` can only add to it); a resume
        that adds entries records the merged policy in a checkpoint before it advances, so a crash
        never drops them.

        A run paused at a human-approval interrupt continues exactly where it stopped: an
        approved call runs once, with the approver's edited arguments if any, and a rejected
        call is fed back to the model as an ``approval:<tool>`` observation so it re-plans.
        With the cancellation file present, the paused run is cancelled instead.

        Args:
            run_id: Existing run identifier.

        Returns:
            Final run result after continuation, or the recorded outcome of a finished run.

        Raises:
            RunNotFoundError: If the event log holds no events for ``run_id``.
            AwaitingApprovalError: If the run is paused at an interrupt nobody decided yet.
            ApprovalError: If the interrupt was already resumed by another process, or the
                approved tool is not registered or allowed in this resume. Nothing was written.
            ResumeError: If an unfinished run has no usable checkpoint or the
                checkpoint's active bot is not registered on this runner.
        """

        recorded = recorded_outcome(self.event_log, run_id)
        if recorded is not None:
            return recorded
        snapshot = load_latest_checkpoint(self.event_log, run_id)
        if snapshot is None:
            if not self.event_log.list_events(run_id):
                raise RunNotFoundError(f"run {run_id} not found in event log {self.event_log.path}")
            raise ResumeError(
                f"cannot resume run {run_id}: it has no checkpoint (it stopped before its first step finished)"
            )
        if not snapshot.goal.strip():
            raise ResumeError(f"cannot resume run {run_id}: its checkpoint is missing a goal")
        if not snapshot.observations:
            raise ResumeError(f"cannot resume run {run_id}: its checkpoint has no observations")

        self.safety_policy.validate_goal(snapshot.goal)
        self._restore_initial_scope()
        if snapshot.active_bot_id is not None:
            bot = self.bots.get(snapshot.active_bot_id)
            if bot is None:
                raise ResumeError(
                    f"cannot resume run {run_id}: checkpoint active bot is not registered: {snapshot.active_bot_id}"
                )
            self.active_bot_id = bot.bot_id
            self.safety_policy = replace(self.safety_policy, allowed_tools=bot.allowed_tools)
        if snapshot.require_approval:
            recorded_policy = self.safety_policy.require_approval | frozenset(snapshot.require_approval)
            self.safety_policy = replace(self.safety_policy, require_approval=recorded_policy)
        if snapshot.interrupt_id is not None:
            return self._resume_interrupt(run_id, snapshot)
        restated = self._with_merged_policy(snapshot)
        if restated is not None:
            self.event_log.append(run_id, restated.state, EventType.CHECKPOINT, restated.to_payload())
        return self._run_loop(
            run_id,
            snapshot.goal,
            snapshot.observations,
            RunStateMachine(),
            start_step=max(0, snapshot.step),
        )

    def fork(
        self,
        source_run_id: str,
        at_step: int,
        new_run_id: str,
        *,
        goal: str | None = None,
        bot_id: str | None = None,
    ) -> RunResult:
        """Branch a recorded run after ``at_step`` into a new run and continue it.

        The state after ``at_step`` is rebuilt from the event log alone (the latest checkpoint
        recorded for that step; step 0 of an original run is its goal), without calling the
        provider. The new run starts with a ``run_forked`` lineage event, then copies of the
        source's events up to that point, then a checkpoint of its own starting state, then its
        own steps from ``at_step`` on, with this runner's provider and step budget
        (``SafetyPolicy.max_steps`` counts the inherited steps). The source run is not modified,
        and it does not need to be finished.

        Every check in :func:`multi_bot_agentic.fork.plan_fork` runs before anything is written.

        Args:
            source_run_id: Run to branch from.
            at_step: Step to branch after (``0`` starts over from the goal).
            new_run_id: Run id of the fork; it must not exist yet.
            goal: New goal; the provider answers it before acting on earlier directives.
            bot_id: Registered bot to continue as. The switch is recorded as a handoff, so
                the first new step is a model call under that bot's scope.

        Returns:
            Final result of the fork.

        Raises:
            ForkError: If the fork is not allowed; nothing has been written.
        """

        self._restore_initial_scope()
        plan = plan_fork(
            self.event_log,
            source_run_id,
            at_step,
            new_run_id,
            provider=self.provider.provider_name,
            policy=replace(self.safety_policy, allowed_tools=self._policy_allowed_tools),
            bots=self.bots,
            goal=goal,
            bot_id=bot_id,
        )
        self.event_log.append(new_run_id, RunState.CREATED, EventType.RUN_FORKED, dict(plan.lineage))
        for event in plan.point.prefix:
            self.event_log.append(new_run_id, RunState(event.state), EventType(event.event_type), event.payload)
        if plan.handoff is not None:
            self.event_log.append(new_run_id, RunState.CREATED, EventType.ACTION_RESULT, dict(plan.handoff))
        # The fork's own starting state: a fork that dies in its first step resumes with its overrides.
        save_checkpoint(
            self.event_log,
            run_id=new_run_id,
            goal=plan.goal,
            step=plan.at_step,
            state=RunState.CREATED,
            observations=plan.observations,
            active_bot_id=plan.bot,
            require_approval=plan.require_approval,
        )
        self.active_bot_id = plan.bot
        self.safety_policy = replace(
            self.safety_policy, allowed_tools=plan.allowed_tools, require_approval=frozenset(plan.require_approval)
        )
        return self._run_loop(new_run_id, plan.goal, plan.observations, RunStateMachine(), start_step=plan.at_step)

    def _run_loop(
        self,
        run_id: str,
        goal: str,
        observations: tuple[Observation, ...],
        state_machine: RunStateMachine,
        start_step: int,
    ) -> RunResult:
        """Drive Observe -> Decide -> Act iterations shared by ``run`` and ``resume``.

        Args:
            run_id: Run identifier.
            goal: User goal.
            observations: Observations accumulated so far.
            state_machine: Run state machine for this invocation.
            start_step: Zero-based step to start from.

        Returns:
            Final run result.
        """

        try:
            for step in range(start_step, self.safety_policy.max_steps):
                self.safety_policy.validate_step(step)
                if self.safety_policy.is_cancelled():
                    return self._cancel(run_id, state_machine, step, "cancellation requested")

                self._transition(run_id, state_machine, RunState.OBSERVING)
                for observation in observations:
                    self.event_log.append(
                        run_id,
                        state_machine.state,
                        EventType.OBSERVATION,
                        observation.to_dict(),
                    )

                self._transition(run_id, state_machine, RunState.DECIDING)
                decision = self.decision_engine.decide(observations, step, self.safety_policy)
                self.event_log.append(
                    run_id,
                    state_machine.state,
                    EventType.DECISION,
                    decision.to_dict(),
                )

                if decision.action == "finish":
                    return self._succeed(run_id, state_machine, step + 1, decision)
                if decision.action == "cancel":
                    return self._cancel(
                        run_id,
                        state_machine,
                        step + 1,
                        str(decision.payload.get("reason", "cancelled")),
                    )
                if decision.action == "fail":
                    return self._fail(
                        run_id,
                        state_machine,
                        step + 1,
                        str(decision.payload.get("reason", "failed")),
                    )

                if decision.action == "call_tool":
                    matched = self._approval_patterns(decision)
                    if matched:
                        return self._interrupt(run_id, state_machine, goal, observations, decision, step, matched)

                self._transition(run_id, state_machine, RunState.ACTING)
                if decision.action == "handoff":
                    new_observation = self._handoff(run_id, state_machine.state, decision)
                else:
                    new_observation = self._act(run_id, state_machine.state, goal, observations, decision)
                observations = (*observations, new_observation)
                save_checkpoint(
                    self.event_log,
                    run_id=run_id,
                    goal=goal,
                    step=step + 1,
                    state=state_machine.state,
                    observations=observations,
                    active_bot_id=self.active_bot_id,
                    require_approval=self.safety_policy.require_approval,
                )

        except (InvalidTransitionError, SafetyError, OSError, RuntimeError, ValueError) as error:
            return self._fail(run_id, state_machine, self.safety_policy.max_steps, str(error))

        return self._fail(run_id, state_machine, self.safety_policy.max_steps, "step budget exhausted")

    def _restore_initial_scope(self) -> None:
        """Return to the constructor's active bot and tool allowlist before a run starts or resumes.

        Handoffs and ``resume`` change ``active_bot_id``, the live allowlist, and the approval
        policy for the current run only. Only ``allowed_tools`` and ``require_approval`` are
        reset, so other policy fields keep their current values.
        """

        self.active_bot_id = self._initial_bot_id
        self.safety_policy = replace(
            self.safety_policy,
            allowed_tools=self._initial_allowed_tools,
            require_approval=self._initial_require_approval,
        )

    def _approval_patterns(self, decision: Decision) -> tuple[str, ...]:
        """Return the ``require_approval`` entries that match a ``call_tool`` decision's tool."""

        if decision.target is None:
            return ()
        return tuple(
            sorted(pattern for pattern in self.safety_policy.require_approval if fnmatchcase(decision.target, pattern))
        )

    def _interrupt(
        self,
        run_id: str,
        state_machine: RunStateMachine,
        goal: str,
        observations: tuple[Observation, ...],
        decision: Decision,
        step: int,
        matched: tuple[str, ...],
    ) -> RunResult:
        """Pause the run before a tool call that needs a human decision.

        The tool is checked against the allowlist and registry first, so a human is never asked
        to approve a call that could not run. Nothing is executed: the run moves to
        ``awaiting_approval``, records an ``interrupt`` event, and checkpoints the paused step, all in
        one transaction, so a process that dies while pausing never leaves an interrupt without the
        checkpoint (and approval policy) that resume restores.

        Args:
            run_id: Run identifier.
            state_machine: Run state machine (``deciding``).
            goal: User goal.
            observations: Observations the decision used.
            decision: The gated ``call_tool`` decision.
            step: Zero-based loop step being paused.
            matched: Policy entries that matched the tool.

        Returns:
            Result in state ``awaiting_approval`` with the interrupt.
        """

        self._tool_for(decision)
        previous, current = state_machine.transition_to(RunState.AWAITING_APPROVAL)
        interrupt_id = new_interrupt_id()
        checkpoint = CheckpointSnapshot(
            run_id=run_id,
            goal=goal,
            step=step,
            state=current,
            observations=observations,
            active_bot_id=self.active_bot_id,
            require_approval=tuple(sorted(self.safety_policy.require_approval)),
            interrupt_id=interrupt_id,
        )
        self.event_log.append_guarded(
            run_id,
            [
                (current, EventType.STATE_TRANSITION, {"from": previous.value, "to": current.value}),
                (
                    current,
                    EventType.INTERRUPT,
                    interrupt_payload(
                        decision, interrupt_id=interrupt_id, step=step + 1, bot=self.active_bot_id, policy=matched
                    ),
                ),
                (current, EventType.CHECKPOINT, checkpoint.to_payload()),
            ],
        )
        return RunResult(
            run_id=run_id,
            state=state_machine.state,
            answer=f"paused: {decision.target} needs human approval (interrupt {interrupt_id})",
            steps=step,
            interrupt=find_interrupt(self.event_log, interrupt_id, run_id=run_id),
        )

    def _resume_interrupt(self, run_id: str, snapshot: CheckpointSnapshot) -> RunResult:
        """Continue a run from the interrupt its latest checkpoint paused at.

        The first write is an atomic claim (it fails if anything happened since the pause), so
        two concurrent resumes can never both run the approved call. A resume that finds an
        earlier claim never executes the call again: it continues from the recorded tool result,
        or refuses when no result was recorded.

        Args:
            run_id: Run identifier.
            snapshot: The interrupt checkpoint (``step`` is the paused zero-based step).

        Returns:
            Final (or next paused) run result.
        """

        events = self.event_log.list_events(run_id)
        record = next(
            (item for item in collect_interrupts(events) if item.interrupt_id == snapshot.interrupt_id),
            None,
        )
        if record is None:
            raise ApprovalError(f"checkpoint of run {run_id} references unknown interrupt {snapshot.interrupt_id}")
        step = snapshot.step
        if not record.paused:
            return self._recover_interrupt(run_id, snapshot, record, events)
        state_machine = RunStateMachine(RunState.AWAITING_APPROVAL)
        if self.safety_policy.is_cancelled():
            return self._cancel(run_id, state_machine, step, "cancellation requested")
        if record.decision is None:
            raise AwaitingApprovalError(record)
        try:
            self.safety_policy.validate_step(step)
        except SafetyError as error:
            return self._fail(run_id, state_machine, step, str(error))

        if record.decision.decision is ApprovalDecision.REJECTED:
            observations = (*snapshot.observations, rejection_observation(record))
            checkpoint = self._next_checkpoint(snapshot, state_machine.state, observations)
            self._claim(run_id, record, [(state_machine.state, EventType.CHECKPOINT, checkpoint.to_payload())])
            return self._run_loop(run_id, snapshot.goal, observations, state_machine, start_step=step + 1)

        interrupt_event = next(event for event in events if event.seq == record.seq)
        decision = Decision(
            action="call_tool",
            target=record.tool,
            payload=dict(record.effective_arguments),
            rationale=_rationale(interrupt_event.payload.get("rationale")),
        )
        try:
            self._tool_for(decision)
        except (SafetyError, ValueError) as error:
            raise ApprovalError(
                f"cannot run approved interrupt {record.interrupt_id}: {error}; "
                "resume with the same tools as the run (for example the same --mcp-config)"
            ) from error
        previous, current = state_machine.transition_to(RunState.ACTING)
        requested = decision.to_dict() | {"interrupt_id": record.interrupt_id}
        restated = self._with_merged_policy(snapshot)
        policy = [] if restated is None else [(restated.state, EventType.CHECKPOINT, restated.to_payload())]
        self._claim(
            run_id,
            record,
            [
                *policy,
                (current, EventType.STATE_TRANSITION, {"from": previous.value, "to": current.value}),
                (current, EventType.ACTION_REQUESTED, requested),
            ],
        )
        try:
            observation = self._execute_tool(run_id, current, decision, interrupt_id=record.interrupt_id)
        except (InvalidTransitionError, SafetyError, OSError, RuntimeError, ValueError) as error:
            return self._fail(run_id, state_machine, step + 1, str(error))
        observations = (*snapshot.observations, observation)
        self.event_log.append(
            run_id,
            current,
            EventType.CHECKPOINT,
            self._next_checkpoint(snapshot, current, observations).to_payload(),
        )
        return self._run_loop(run_id, snapshot.goal, observations, state_machine, start_step=step + 1)

    def _recover_interrupt(
        self,
        run_id: str,
        snapshot: CheckpointSnapshot,
        record: InterruptRecord,
        events: Sequence[EventRecord],
    ) -> RunResult:
        """Continue after an earlier resume of this interrupt stopped before its next checkpoint.

        An approved call whose result was recorded is never executed again: the recorded result
        becomes the observation. Anything else (the call started but recorded no result, or
        another resume is still running) is refused without writing.
        """

        result = next(
            (
                event
                for event in reversed(events)
                if event.event_type == EventType.ACTION_RESULT.value
                and event.payload.get("interrupt_id") == record.interrupt_id
            ),
            None,
        )
        if record.decision is None or record.decision.decision is not ApprovalDecision.APPROVED or result is None:
            raise ApprovalError(
                f"interrupt {record.interrupt_id} of run {run_id} was already resumed and recorded no result; "
                "an approved call is never executed twice. If that resume crashed, fork the run after "
                f"step {snapshot.step} to try again"
            )
        payload = result.payload
        metadata = payload.get("metadata")
        observation = ToolResult(
            tool_name=str(payload.get("tool") or record.tool),
            ok=bool(payload.get("ok")),
            content=str(payload.get("content", "")),
            metadata=dict(metadata) if isinstance(metadata, dict) else {},
        ).to_observation()
        state_machine = RunStateMachine(RunState.ACTING)
        observations = (*snapshot.observations, observation)
        self.event_log.append(
            run_id,
            state_machine.state,
            EventType.CHECKPOINT,
            self._next_checkpoint(snapshot, state_machine.state, observations).to_payload(),
        )
        return self._run_loop(run_id, snapshot.goal, observations, state_machine, start_step=snapshot.step + 1)

    def _with_merged_policy(self, snapshot: CheckpointSnapshot) -> CheckpointSnapshot | None:
        """Return ``snapshot`` restated with this resume's approval policy, or ``None`` if it did not grow.

        A resume records the restated checkpoint before it advances (inside the claim at an interrupt),
        so ``require_approval`` entries it added survive a crash before its next checkpoint.
        """

        merged = tuple(sorted(self.safety_policy.require_approval))
        if set(merged) == set(snapshot.require_approval):
            return None
        return replace(snapshot, require_approval=merged)

    def _next_checkpoint(
        self,
        snapshot: CheckpointSnapshot,
        state: RunState,
        observations: tuple[Observation, ...],
    ) -> CheckpointSnapshot:
        """Return the checkpoint that closes a paused step."""

        return CheckpointSnapshot(
            run_id=snapshot.run_id,
            goal=snapshot.goal,
            step=snapshot.step + 1,
            state=state,
            observations=observations,
            active_bot_id=self.active_bot_id,
            require_approval=tuple(sorted(self.safety_policy.require_approval)),
        )

    def _claim(
        self,
        run_id: str,
        record: InterruptRecord,
        entries: Sequence[tuple[RunState, EventType, dict[str, Any]]],
    ) -> None:
        """Append the first events of a resume only if the run is still paused at ``record``.

        Raises:
            ApprovalError: If another process resumed the interrupt first.
        """

        def guard(events: list[EventRecord]) -> None:
            current = next(
                (item for item in collect_interrupts(events) if item.interrupt_id == record.interrupt_id), None
            )
            if current is None or not current.paused:
                raise ApprovalError(
                    f"interrupt {record.interrupt_id} of run {run_id} was resumed by another process; "
                    "nothing was executed here"
                )

        self.event_log.append_guarded(run_id, entries, guard)

    def _handoff(self, run_id: str, state: RunState, decision: Decision) -> Observation:
        """Switch the active bot and scoped tool allowlist.

        Args:
            run_id: Run identifier.
            state: Current state.
            decision: Handoff decision.

        Returns:
            Observation describing the handoff.

        Raises:
            ValueError: If the target bot is missing or unregistered.
        """

        if decision.target is None:
            raise ValueError("handoff decision requires a target bot id")
        bot = self.bots.get(decision.target)
        if bot is None:
            raise ValueError(f"handoff target bot is not registered: {decision.target}")
        previous = self.active_bot_id
        self.active_bot_id = bot.bot_id
        self.safety_policy = replace(self.safety_policy, allowed_tools=bot.allowed_tools)
        summary = str(decision.payload.get("summary", ""))
        self.event_log.append(
            run_id,
            state,
            EventType.ACTION_RESULT,
            {
                "kind": "handoff",
                "from_bot": previous,
                "to_bot": bot.bot_id,
                "summary": summary,
                "allowed_tools": sorted(bot.allowed_tools),
            },
        )
        return Observation(
            source=f"handoff:{bot.bot_id}",
            content=f"HANDED_OFF:{bot.bot_id}:{summary}",
            metadata={"from_bot": previous, "to_bot": bot.bot_id, "summary": summary},
        )

    def _act(
        self,
        run_id: str,
        state: RunState,
        goal: str,
        observations: tuple[Observation, ...],
        decision: Decision,
    ) -> Observation:
        """Execute a provider or tool action.

        Args:
            run_id: Run identifier.
            state: Current state.
            goal: User goal.
            observations: Current observations.
            decision: Selected decision.

        Returns:
            New observation produced by the action.
        """

        self.event_log.append(run_id, state, EventType.ACTION_REQUESTED, decision.to_dict())
        if decision.action == "call_llm":
            output = self.provider.complete(
                ModelRequest(goal=goal, observations=observations, tools=self._visible_tool_specs()),
                timeout_seconds=self.safety_policy.timeout_seconds,
            )
            observation = output.to_observation()
            self.event_log.append(
                run_id,
                state,
                EventType.ACTION_RESULT,
                {"kind": "llm", "output": output.text, "metadata": output.raw},
            )
            return observation

        if decision.action == "call_tool":
            return self._execute_tool(run_id, state, decision)

        raise ValueError(f"unsupported action for _act: {decision.action}")

    def _tool_for(self, decision: Decision) -> ToolAdapter:
        """Return the registered, allowlisted tool a ``call_tool`` decision targets.

        Raises:
            SafetyError: If the tool is not allowlisted.
            ValueError: If the decision has no target or the tool is not registered.
        """

        if decision.target is None:
            raise ValueError("tool decision requires a target")
        self.safety_policy.validate_tool(decision.target)
        tool = self.tools.get(decision.target)
        if tool is None:
            raise ValueError(f"tool is not registered: {decision.target}")
        return tool

    def _execute_tool(
        self,
        run_id: str,
        state: RunState,
        decision: Decision,
        interrupt_id: str | None = None,
    ) -> Observation:
        """Execute a tool call and record its result (tagged with the interrupt it was approved in).

        Args:
            run_id: Run identifier.
            state: Current state.
            decision: ``call_tool`` decision.
            interrupt_id: Interrupt that approved the call, if any.

        Returns:
            Observation of the tool result.
        """

        tool = self._tool_for(decision)
        result = tool.execute(ToolInvocation(tool_name=str(decision.target), arguments=decision.payload))
        payload: dict[str, Any] = {
            "kind": "tool",
            "tool": result.tool_name,
            "ok": result.ok,
            "content": result.content,
            "metadata": result.metadata,
        }
        if interrupt_id is not None:
            payload["interrupt_id"] = interrupt_id
        self.event_log.append(run_id, state, EventType.ACTION_RESULT, payload)
        return result.to_observation()

    def _visible_tool_specs(self) -> tuple[ToolSpec, ...]:
        """Return advertised tool specs that are registered and currently allowed.

        Returns:
            Tool specs the provider may see for the next model call.
        """

        allowed = self.safety_policy.allowed_tools
        return tuple(spec for spec in self.tool_specs if spec.name in allowed and spec.name in self.tools)

    def _transition(
        self,
        run_id: str,
        state_machine: RunStateMachine,
        next_state: RunState,
    ) -> None:
        """Transition and persist state-machine movement.

        Args:
            run_id: Run identifier.
            state_machine: Run state machine.
            next_state: Desired state.
        """

        previous_state, current_state = state_machine.transition_to(next_state)
        self.event_log.append(
            run_id,
            current_state,
            EventType.STATE_TRANSITION,
            {"from": previous_state.value, "to": current_state.value},
        )

    def _succeed(
        self,
        run_id: str,
        state_machine: RunStateMachine,
        steps: int,
        decision: Decision,
    ) -> RunResult:
        """Mark a run as succeeded.

        Args:
            run_id: Run identifier.
            state_machine: Run state machine.
            steps: Step count.
            decision: Finish decision.

        Returns:
            Successful run result.
        """

        self._transition(run_id, state_machine, RunState.SUCCEEDED)
        answer = str(decision.payload.get("answer", ""))
        self.event_log.append(
            run_id,
            state_machine.state,
            EventType.RUN_COMPLETED,
            {"answer": answer, "steps": steps},
        )
        return RunResult(run_id=run_id, state=state_machine.state, answer=answer, steps=steps)

    def _cancel(
        self,
        run_id: str,
        state_machine: RunStateMachine,
        steps: int,
        reason: str,
    ) -> RunResult:
        """Mark a run as cancelled.

        Args:
            run_id: Run identifier.
            state_machine: Run state machine.
            steps: Step count.
            reason: Cancellation reason.

        Returns:
            Cancelled run result.
        """

        self._transition(run_id, state_machine, RunState.CANCELLED)
        self.event_log.append(
            run_id,
            state_machine.state,
            EventType.RUN_CANCELLED,
            {"reason": reason, "steps": steps},
        )
        return RunResult(run_id=run_id, state=state_machine.state, answer=reason, steps=steps)

    def _fail(
        self,
        run_id: str,
        state_machine: RunStateMachine,
        steps: int,
        reason: str,
    ) -> RunResult:
        """Mark a run as failed.

        Args:
            run_id: Run identifier.
            state_machine: Run state machine.
            steps: Step count.
            reason: Failure reason.

        Returns:
            Failed run result.
        """

        if not state_machine.is_terminal():
            self._transition(run_id, state_machine, RunState.FAILED)
        self.event_log.append(
            run_id,
            state_machine.state,
            EventType.RUN_FAILED,
            {"reason": reason, "steps": steps},
        )
        return RunResult(run_id=run_id, state=state_machine.state, answer=reason, steps=steps)


def _rationale(value: Any) -> RationaleTrace:
    """Rebuild the rationale trace an ``interrupt`` event recorded for the paused decision."""

    payload = value if isinstance(value, dict) else {}
    used = payload.get("observations_used")
    rejected = payload.get("rejected_actions")
    return RationaleTrace(
        rule_id=str(payload.get("rule_id", "")),
        observations_used=tuple(str(item) for item in used) if isinstance(used, list) else (),
        rejected_actions=tuple(str(item) for item in rejected) if isinstance(rejected, list) else (),
        explanation=str(payload.get("explanation", "")),
    )


def build_default_tools(root: Path) -> dict[str, ToolAdapter]:
    """Build default allowlisted tools.

    Args:
        root: Root directory for read-only file access.

    Returns:
        Tool registry.
    """

    from multi_bot_agentic.tools.base32_encode import Base32EncodeTool
    from multi_bot_agentic.tools.base58 import Base58Tool
    from multi_bot_agentic.tools.base64_codec import Base64Tool
    from multi_bot_agentic.tools.base85 import Base85Tool
    from multi_bot_agentic.tools.braille import BrailleTool
    from multi_bot_agentic.tools.caesar_cipher import CaesarCipherTool
    from multi_bot_agentic.tools.calculator import CalculatorTool
    from multi_bot_agentic.tools.checklist import ChecklistTool
    from multi_bot_agentic.tools.content_type_sniff import ContentTypeSniffTool
    from multi_bot_agentic.tools.crc32 import Crc32Tool
    from multi_bot_agentic.tools.cron_next import CronNextTool
    from multi_bot_agentic.tools.csv_diff import CsvDiffTool
    from multi_bot_agentic.tools.csv_fillna import CsvFillnaTool
    from multi_bot_agentic.tools.csv_filter import CsvFilterTool
    from multi_bot_agentic.tools.csv_groupby import CsvGroupbyTool
    from multi_bot_agentic.tools.csv_join import CsvJoinTool
    from multi_bot_agentic.tools.csv_melt import CsvMeltTool
    from multi_bot_agentic.tools.csv_parse import CsvParseTool
    from multi_bot_agentic.tools.csv_pivot import CsvPivotTool
    from multi_bot_agentic.tools.csv_select_columns import CsvSelectColumnsTool
    from multi_bot_agentic.tools.csv_sort import CsvSortTool
    from multi_bot_agentic.tools.csv_stack import CsvStackTool
    from multi_bot_agentic.tools.csv_to_json import CsvToJsonTool
    from multi_bot_agentic.tools.csv_transpose import CsvTransposeTool
    from multi_bot_agentic.tools.csv_tsv import CsvTsvTool
    from multi_bot_agentic.tools.csv_unique import CsvUniqueTool
    from multi_bot_agentic.tools.csv_window import CsvWindowTool
    from multi_bot_agentic.tools.datetime_normalize import DateTimeTool
    from multi_bot_agentic.tools.diff_text import DiffTool
    from multi_bot_agentic.tools.duration_parse import DurationTool
    from multi_bot_agentic.tools.echo import EchoTool
    from multi_bot_agentic.tools.filesystem_readonly import ReadOnlyFileTool
    from multi_bot_agentic.tools.geohash import GeohashTool
    from multi_bot_agentic.tools.hashing import HashTool
    from multi_bot_agentic.tools.hex_encode import HexEncodeTool
    from multi_bot_agentic.tools.hmac_sign import HmacSignTool
    from multi_bot_agentic.tools.html_attr_extract import HtmlAttrExtractTool
    from multi_bot_agentic.tools.html_entities import HtmlEntitiesTool
    from multi_bot_agentic.tools.html_links_extract import HtmlLinksExtractTool
    from multi_bot_agentic.tools.html_markdown import HtmlMarkdownTool
    from multi_bot_agentic.tools.html_strip import HtmlStripTool
    from multi_bot_agentic.tools.html_table import HtmlTableTool
    from multi_bot_agentic.tools.html_table_csv import HtmlTableCsvTool
    from multi_bot_agentic.tools.iban_check import IbanCheckTool
    from multi_bot_agentic.tools.ics_parse import IcsParseTool
    from multi_bot_agentic.tools.ini_parse import IniParseTool
    from multi_bot_agentic.tools.isbn13 import Isbn13Tool
    from multi_bot_agentic.tools.jaro_winkler import JaroWinklerTool
    from multi_bot_agentic.tools.json_diff_paths import JsonDiffPathsTool
    from multi_bot_agentic.tools.json_flatten import JsonFlattenTool
    from multi_bot_agentic.tools.json_format import JsonFormatTool
    from multi_bot_agentic.tools.json_merge_patch import JsonMergePatchTool
    from multi_bot_agentic.tools.json_patch_apply import JsonPatchApplyTool
    from multi_bot_agentic.tools.json_path import JsonPathTool
    from multi_bot_agentic.tools.json_pointer import JsonPointerTool
    from multi_bot_agentic.tools.json_query import JsonQueryTool
    from multi_bot_agentic.tools.json_unflatten import JsonUnflattenTool
    from multi_bot_agentic.tools.jsonl_parse import JsonlParseTool
    from multi_bot_agentic.tools.jwt_decode import JwtDecodeTool
    from multi_bot_agentic.tools.jwt_encode import JwtEncodeTool
    from multi_bot_agentic.tools.levenshtein import LevenshteinTool
    from multi_bot_agentic.tools.line_number import LineNumberTool
    from multi_bot_agentic.tools.luhn import LuhnTool
    from multi_bot_agentic.tools.markdown_table import MarkdownTableTool
    from multi_bot_agentic.tools.markdown_toc import MarkdownTocTool
    from multi_bot_agentic.tools.metaphone import MetaphoneTool
    from multi_bot_agentic.tools.mime_attachment_cid_map import MimeAttachmentCidMapTool
    from multi_bot_agentic.tools.mime_attachment_ctypes import MimeAttachmentCtypesTool
    from multi_bot_agentic.tools.mime_attachment_disposition import MimeAttachmentDispositionTool
    from multi_bot_agentic.tools.mime_attachment_encoding import MimeAttachmentEncodingTool
    from multi_bot_agentic.tools.mime_attachment_filenames_unique import MimeAttachmentFilenamesUniqueTool
    from multi_bot_agentic.tools.mime_attachment_names import MimeAttachmentNamesTool
    from multi_bot_agentic.tools.mime_attachment_sizes import MimeAttachmentSizesTool
    from multi_bot_agentic.tools.mime_multipart import MimeMultipartTool
    from multi_bot_agentic.tools.mime_multipart_flatten import MimeMultipartFlattenTool
    from multi_bot_agentic.tools.mime_part_headers import MimePartHeadersTool
    from multi_bot_agentic.tools.morse import MorseTool
    from multi_bot_agentic.tools.nato_phonetic import NatoPhoneticTool
    from multi_bot_agentic.tools.pluralize import PluralizeTool
    from multi_bot_agentic.tools.punycode import PunycodeTool
    from multi_bot_agentic.tools.redaction import RedactionTool
    from multi_bot_agentic.tools.regex_extract import RegexExtractTool
    from multi_bot_agentic.tools.regex_replace import RegexReplaceTool
    from multi_bot_agentic.tools.roman_numeral import RomanNumeralTool
    from multi_bot_agentic.tools.rot13 import Rot13Tool
    from multi_bot_agentic.tools.semver_compare import SemverCompareTool
    from multi_bot_agentic.tools.slugify import SlugifyTool
    from multi_bot_agentic.tools.soundex import SoundexTool
    from multi_bot_agentic.tools.spreadsheet_slice import SpreadsheetSliceTool
    from multi_bot_agentic.tools.template_render import TemplateRenderTool
    from multi_bot_agentic.tools.text_case import TextCaseTool
    from multi_bot_agentic.tools.text_center_lines import TextCenterLinesTool
    from multi_bot_agentic.tools.text_collapse_blank import TextCollapseBlankTool
    from multi_bot_agentic.tools.text_dedent import TextDedentTool
    from multi_bot_agentic.tools.text_indent import TextIndentTool
    from multi_bot_agentic.tools.text_justify_lines import TextJustifyLinesTool
    from multi_bot_agentic.tools.text_margin_lines import TextMarginLinesTool
    from multi_bot_agentic.tools.text_outdent import TextOutdentTool
    from multi_bot_agentic.tools.text_pad_lines import TextPadLinesTool
    from multi_bot_agentic.tools.text_slug_lines import TextSlugLinesTool
    from multi_bot_agentic.tools.text_sort_lines import TextSortLinesTool
    from multi_bot_agentic.tools.text_squeeze_ws import TextSqueezeWsTool
    from multi_bot_agentic.tools.text_title_lines import TextTitleLinesTool
    from multi_bot_agentic.tools.text_truncate import TextTruncateTool
    from multi_bot_agentic.tools.text_unique_lines import TextUniqueLinesTool
    from multi_bot_agentic.tools.text_wrap import TextWrapTool
    from multi_bot_agentic.tools.toml_format import TomlFormatTool
    from multi_bot_agentic.tools.toml_json import TomlJsonTool
    from multi_bot_agentic.tools.tsv_format import TsvFormatTool
    from multi_bot_agentic.tools.ulid import UlidTool
    from multi_bot_agentic.tools.unicode_normalize import UnicodeNormalizeTool
    from multi_bot_agentic.tools.url_encode import UrlEncodeTool
    from multi_bot_agentic.tools.url_normalize import UrlNormalizeTool
    from multi_bot_agentic.tools.url_parse import UrlParseTool
    from multi_bot_agentic.tools.uuid4 import Uuid4Tool
    from multi_bot_agentic.tools.uuid5 import Uuid5Tool
    from multi_bot_agentic.tools.uuid_nil import UuidNilTool
    from multi_bot_agentic.tools.xml_escape import XmlEscapeTool
    from multi_bot_agentic.tools.xml_parse import XmlParseTool
    from multi_bot_agentic.tools.yaml_format import YamlFormatTool
    from multi_bot_agentic.tools.yaml_to_json import YamlToJsonTool
    from multi_bot_agentic.tools.zip_list import ZipListTool

    return {
        "base32_encode": Base32EncodeTool(),
        "base58": Base58Tool(),
        "base64": Base64Tool(),
        "base85": Base85Tool(),
        "braille": BrailleTool(),
        "caesar_cipher": CaesarCipherTool(),
        "calculator": CalculatorTool(),
        "checklist": ChecklistTool(),
        "content_type_sniff": ContentTypeSniffTool(),
        "crc32": Crc32Tool(),
        "cron_next": CronNextTool(),
        "csv": CsvParseTool(),
        "csv_diff": CsvDiffTool(),
        "csv_fillna": CsvFillnaTool(),
        "csv_filter": CsvFilterTool(),
        "csv_groupby": CsvGroupbyTool(),
        "csv_join": CsvJoinTool(),
        "csv_melt": CsvMeltTool(),
        "csv_pivot": CsvPivotTool(),
        "csv_select_columns": CsvSelectColumnsTool(),
        "csv_sort": CsvSortTool(),
        "csv_stack": CsvStackTool(),
        "csv_to_json": CsvToJsonTool(),
        "csv_transpose": CsvTransposeTool(),
        "csv_tsv": CsvTsvTool(),
        "csv_unique": CsvUniqueTool(),
        "csv_window": CsvWindowTool(),
        "datetime": DateTimeTool(),
        "diff": DiffTool(),
        "duration": DurationTool(),
        "echo": EchoTool(),
        "geohash": GeohashTool(),
        "hash": HashTool(),
        "hex_encode": HexEncodeTool(),
        "hmac_sign": HmacSignTool(),
        "html_attr_extract": HtmlAttrExtractTool(),
        "html_entities": HtmlEntitiesTool(),
        "html_links_extract": HtmlLinksExtractTool(),
        "html_markdown": HtmlMarkdownTool(),
        "html_strip": HtmlStripTool(),
        "html_table": HtmlTableTool(),
        "html_table_csv": HtmlTableCsvTool(),
        "iban_check": IbanCheckTool(),
        "ics_parse": IcsParseTool(),
        "ini_parse": IniParseTool(),
        "isbn13": Isbn13Tool(),
        "jaro_winkler": JaroWinklerTool(),
        "json_diff_paths": JsonDiffPathsTool(),
        "json_flatten": JsonFlattenTool(),
        "json_format": JsonFormatTool(),
        "json_merge_patch": JsonMergePatchTool(),
        "json_patch_apply": JsonPatchApplyTool(),
        "json_path": JsonPathTool(),
        "json_pointer": JsonPointerTool(),
        "json_query": JsonQueryTool(),
        "json_unflatten": JsonUnflattenTool(),
        "jsonl_parse": JsonlParseTool(),
        "jwt_decode": JwtDecodeTool(),
        "jwt_encode": JwtEncodeTool(),
        "levenshtein": LevenshteinTool(),
        "line_number": LineNumberTool(),
        "luhn": LuhnTool(),
        "markdown_table": MarkdownTableTool(),
        "markdown_toc": MarkdownTocTool(),
        "metaphone": MetaphoneTool(),
        "mime_attachment_cid_map": MimeAttachmentCidMapTool(),
        "mime_attachment_ctypes": MimeAttachmentCtypesTool(),
        "mime_attachment_disposition": MimeAttachmentDispositionTool(),
        "mime_attachment_encoding": MimeAttachmentEncodingTool(),
        "mime_attachment_filenames_unique": MimeAttachmentFilenamesUniqueTool(),
        "mime_attachment_names": MimeAttachmentNamesTool(),
        "mime_attachment_sizes": MimeAttachmentSizesTool(),
        "mime_multipart": MimeMultipartTool(),
        "mime_multipart_flatten": MimeMultipartFlattenTool(),
        "mime_part_headers": MimePartHeadersTool(),
        "morse": MorseTool(),
        "nato_phonetic": NatoPhoneticTool(),
        "pluralize": PluralizeTool(),
        "punycode": PunycodeTool(),
        "readonly_file": ReadOnlyFileTool(root=root),
        "redact": RedactionTool(),
        "regex": RegexExtractTool(),
        "regex_replace": RegexReplaceTool(),
        "roman_numeral": RomanNumeralTool(),
        "rot13": Rot13Tool(),
        "semver_compare": SemverCompareTool(),
        "slugify": SlugifyTool(),
        "soundex": SoundexTool(),
        "spreadsheet_slice": SpreadsheetSliceTool(),
        "template_render": TemplateRenderTool(),
        "text_case": TextCaseTool(),
        "text_center_lines": TextCenterLinesTool(),
        "text_collapse_blank": TextCollapseBlankTool(),
        "text_dedent": TextDedentTool(),
        "text_indent": TextIndentTool(),
        "text_justify_lines": TextJustifyLinesTool(),
        "text_margin_lines": TextMarginLinesTool(),
        "text_outdent": TextOutdentTool(),
        "text_pad_lines": TextPadLinesTool(),
        "text_slug_lines": TextSlugLinesTool(),
        "text_sort_lines": TextSortLinesTool(),
        "text_squeeze_ws": TextSqueezeWsTool(),
        "text_title_lines": TextTitleLinesTool(),
        "text_unique_lines": TextUniqueLinesTool(),
        "text_wrap": TextWrapTool(),
        "toml_format": TomlFormatTool(),
        "toml_json": TomlJsonTool(),
        "truncate": TextTruncateTool(),
        "tsv_format": TsvFormatTool(),
        "ulid": UlidTool(),
        "unicode_normalize": UnicodeNormalizeTool(),
        "url_encode": UrlEncodeTool(),
        "url_normalize": UrlNormalizeTool(),
        "url_parse": UrlParseTool(),
        "uuid4": Uuid4Tool(),
        "uuid5": Uuid5Tool(),
        "uuid_nil": UuidNilTool(),
        "xml_escape": XmlEscapeTool(),
        "xml_parse": XmlParseTool(),
        "yaml_format": YamlFormatTool(),
        "yaml_to_json": YamlToJsonTool(),
        "zip_list": ZipListTool(),
    }
