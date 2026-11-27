"""Observe -> Decide -> Act runner."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import datetime, timezone
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
from multi_bot_agentic.event_log import EventRecord, RunLease, SQLiteEventLog
from multi_bot_agentic.fork import ForkPlan, plan_fork
from multi_bot_agentic.lifecycle import InvalidTransitionError, RunStateMachine
from multi_bot_agentic.llm.base import BilledCallError, LLMAdapter
from multi_bot_agentic.models import (
    Decision,
    EventType,
    ModelOutput,
    ModelRequest,
    Observation,
    RationaleTrace,
    RunState,
    ToolInvocation,
    ToolResult,
    ToolSpec,
)
from multi_bot_agentic.pricing import PriceTable, price_call
from multi_bot_agentic.safety import SafetyError, SafetyPolicy
from multi_bot_agentic.structured_output import (
    CONTRACT_KEY,
    CORRECTION_SOURCE,
    MAX_ANSWER_CHARS,
    FinalOutput,
    OutputContract,
    OutputSchema,
    SchemaError,
    check_output,
    correction_text,
    failed_attempts,
    recorded_contract,
    recorded_output,
    sha256_of,
    verified_output,
)
from multi_bot_agentic.tools.base import ToolAdapter
from multi_bot_agentic.usage import AFTER_CALL, BEFORE_CALL, LimitBreach, UsageLimits, UsageTotals


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
        output: The validated final output of a succeeded run with an output schema.
        output_errors: Validation errors of the last answer when ``state`` is ``output_invalid``.
        usage: Running usage totals the run's limits count (a fork's include its inherited calls).
        usage_limit: The limit that stopped the run when ``state`` is ``usage_limit_exceeded``.
        still_stopped: True when ``resume`` found the run still over that limit and wrote nothing.
    """

    run_id: str
    state: RunState
    answer: str
    steps: int
    already_finished: bool = False
    interrupt: InterruptRecord | None = None
    output: FinalOutput | None = None
    output_errors: tuple[str, ...] = ()
    usage: UsageTotals | None = None
    usage_limit: LimitBreach | None = None
    still_stopped: bool = False


class ResumeError(ValueError):
    """Raised when ``AgentRunner.resume`` cannot continue a run; nothing is executed or appended.

    It subclasses ``ValueError``, which ``resume`` raised before, so existing handlers keep working.
    """


class RunNotFoundError(ResumeError):
    """Raised when the event log holds no events for the run id to resume."""


class RunBusyError(ResumeError):
    """Raised when another live process is continuing the run; nothing is written.

    ``run``, ``resume`` and ``fork`` hold the run's lease in the event log while they continue it, so
    two processes never both append a run's next steps (duplicating provider calls or tool side effects).

    Attributes:
        holder: Lease of the process that is continuing the run.
    """

    def __init__(self, run_id: str, holder: RunLease) -> None:
        super().__init__(
            f"run {run_id} is being continued by process {holder.pid} on {holder.host} "
            f"(since {holder.acquired_at}); nothing was written. Resume again after it finishes; if that "
            "process is gone but still holds the run (for example it ran on another host), fork the run "
            "to continue it under a new id"
        )
        self.holder = holder


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
        or ``None`` when the run has not finished. A run with an output contract also gets its
        final output (verified: see :func:`verified_output`) or its last validation errors.

    Raises:
        ResumeError: If the run's recorded output contract or final output was changed after the
            run recorded it.
    """

    events = event_log.list_events(run_id)
    terminal: EventRecord | None = None
    for event in events:
        if event.event_type in _TERMINAL_EVENT_STATES:
            terminal = event
    if terminal is None:
        return None
    state = terminal_state(terminal)
    answer = terminal.payload.get("answer" if state is RunState.SUCCEEDED else "reason", "")
    steps = terminal.payload.get("steps")
    try:
        contract = recorded_contract(events)
        output = verified_output(events) if state is RunState.SUCCEEDED else None
    except SchemaError as error:
        raise ResumeError(f"cannot use the recorded outcome of run {run_id}: {error}") from error
    errors: tuple[str, ...] = ()
    if state is RunState.OUTPUT_INVALID and contract is not None:
        _, errors = recorded_output(events, schema_sha256=contract.schema.sha256)
    return RunResult(
        run_id=run_id,
        state=state,
        answer=str(answer),
        steps=steps if isinstance(steps, int) else 0,
        already_finished=True,
        output=output,
        output_errors=errors,
        usage=UsageTotals.from_events(events),
    )


def terminal_state(event: EventRecord) -> RunState:
    """Return the state a terminal event recorded.

    A run whose final answer never validated ends with a ``run_failed`` event in state
    ``output_invalid``; every other terminal event type maps to one state.
    """

    if event.state == RunState.OUTPUT_INVALID.value:
        return RunState.OUTPUT_INVALID
    return _TERMINAL_EVENT_STATES[event.event_type]


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
        price_table: PriceTable | None = None,
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
            price_table: Prices for the cost each ``llm_usage`` event records (default: built-in).
        """

        self.provider = provider
        self.price_table = price_table or PriceTable()
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
        # The output contract of the current run (set by run, resume, and fork) and its failed answers.
        self._contract: OutputContract | None = None
        self._output_failures = 0
        self._initial_usage_limits = self.safety_policy.usage_limits
        self._usage = UsageTotals()
        self.decision_engine = DeterministicDecisionEngine(
            provider_name=provider.provider_name,
            bots=self.bots or None,
        )

    def run(self, goal: str, run_id: str | None = None, *, output_contract: OutputContract | None = None) -> RunResult:
        """Execute one bounded agent run.

        Every run starts with the constructor's ``active_bot_id`` and tool scope. A
        handoff lasts only for the run that made it, so a reused runner never starts a
        run with the scope an earlier ``run`` or ``resume`` left behind.

        With an ``output_contract`` the final answer must be a JSON document that validates
        against its schema. The contract is recorded in the ``run_created`` event, and every
        invalid answer is fed back to the model for another round, up to ``retries`` rounds;
        then the run ends in state ``output_invalid``.

        Args:
            goal: User goal.
            run_id: Optional run identifier; one the event log already holds is refused, so a
                second run is never appended to a recorded one (``resume`` continues a run).
            output_contract: Optional output schema and correction-round budget.

        Returns:
            Final run result.

        Raises:
            RunExistsError: If the event log already holds events for ``run_id``.
            RunBusyError: If another live process holds ``run_id``'s lease; nothing was written.
        """

        self.safety_policy.validate_goal(goal)
        if run_id and self.event_log.list_events(run_id):
            raise RunExistsError(
                f"run {run_id} already exists in event log {self.event_log.path}; "
                "choose a new run id (resume continues an interrupted run)"
            )
        self._restore_initial_scope()
        self._contract, self._output_failures = output_contract, 0
        selected_run_id = run_id or str(uuid4())
        state_machine = RunStateMachine()
        observations: tuple[Observation, ...] = (Observation(source="user", content=goal),)
        created: dict[str, Any] = {"goal": goal, "provider": self.provider.provider_name}
        if self.safety_policy.require_approval:
            created["require_approval"] = sorted(self.safety_policy.require_approval)
        if output_contract is not None:
            created[CONTRACT_KEY] = output_contract.to_payload()
        if self.safety_policy.usage_limits.active:
            created["usage_limits"] = self.safety_policy.usage_limits.to_dict()
        self._usage = UsageTotals()
        with self._sole_owner(selected_run_id):
            self.event_log.append(selected_run_id, state_machine.state, EventType.RUN_CREATED, created)
            return self._run_loop(selected_run_id, goal, observations, state_machine, start_step=0)

    def resume(self, run_id: str, *, reset_usage_limits: bool = False) -> RunResult:
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
        never drops them. The output contract recorded when the run started stays in force too,
        with the correction rounds the run already used.

        A run paused at a human-approval interrupt continues exactly where it stopped: an
        approved call runs once, with the approver's edited arguments if any, and a rejected
        call is fed back to the model as an ``approval:<tool>`` observation so it re-plans.
        With the cancellation file present, the paused run is cancelled instead.

        Only one process continues a run at a time: ``resume`` holds the run's lease in the event
        log while it reads and continues the run, and a second ``resume`` (or one racing the ``run``
        or ``fork`` still executing it) is refused without writing. A lease left behind by a process
        that died is taken over, so a crashed run can still be resumed.

        Usage totals continue from the run's ``llm_usage`` events. The usage limits recorded in the
        checkpoint stay in force; each limit this runner sets replaces the recorded one, so a run
        stopped at a usage limit continues once it is resumed with a higher limit. While the limit
        that stopped it still holds, ``resume`` returns the stop again and writes nothing.

        Args:
            run_id: Existing run identifier.
            reset_usage_limits: Drop the recorded usage limits, so only this runner's apply.

        Returns:
            Final run result after continuation, or the recorded outcome of a finished run.

        Raises:
            RunNotFoundError: If the event log holds no events for ``run_id``.
            RunBusyError: If another live process is continuing the run. Nothing was written.
            AwaitingApprovalError: If the run is paused at an interrupt nobody decided yet.
            ApprovalError: If an earlier resume claimed the approved call but recorded no result, or the
                approved tool is not registered or allowed in this resume. Nothing was written.
            ResumeError: If an unfinished run has no usable checkpoint, the
                checkpoint's active bot is not registered on this runner, or the run's recorded
                output contract is unusable.
        """

        recorded = recorded_outcome(self.event_log, run_id)
        if recorded is not None:
            return recorded
        with self._sole_owner(run_id):
            return self._resume_owned(run_id, reset_usage_limits=reset_usage_limits)

    def _resume_owned(self, run_id: str, *, reset_usage_limits: bool) -> RunResult:
        """Continue ``run_id`` while holding its lease; everything is read again under the lease."""

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
        events = self.event_log.list_events(run_id)
        try:
            self._contract = recorded_contract(events)
        except SchemaError as error:
            raise ResumeError(f"cannot resume run {run_id}: {error}") from error
        self._output_failures = failed_attempts(events, self._contract.schema.sha256) if self._contract else 0
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
        recorded_limits = UsageLimits() if reset_usage_limits else snapshot.usage_limits
        limits = recorded_limits.override(self.safety_policy.usage_limits)
        self.safety_policy = replace(self.safety_policy, usage_limits=limits)
        events = self.event_log.list_events(run_id)
        self._usage = UsageTotals.from_events(events)
        if snapshot.interrupt_id is not None:
            return self._resume_interrupt(run_id, snapshot)
        state_machine = RunStateMachine()
        if snapshot.state is RunState.USAGE_LIMIT_EXCEEDED:
            # Still over the limit that stopped it: report the stop again and write nothing.
            breach = limits.check(self._usage, _stop_phase(events))
            if breach is not None and not self.safety_policy.is_cancelled():
                return RunResult(
                    run_id=run_id,
                    state=RunState.USAGE_LIMIT_EXCEEDED,
                    answer=f"stopped: {breach.message}",
                    steps=snapshot.step,
                    usage=self._usage,
                    usage_limit=breach,
                    still_stopped=True,
                )
            state_machine = RunStateMachine(RunState.USAGE_LIMIT_EXCEEDED)
        restated = self._with_merged_policy(snapshot)
        if restated is not None:
            self.event_log.append(run_id, restated.state, EventType.CHECKPOINT, restated.to_payload())
        return self._run_loop(
            run_id,
            snapshot.goal,
            snapshot.observations,
            state_machine,
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
        output_schema: OutputSchema | None = None,
        output_retries: int | None = None,
        reset_usage_limits: bool = False,
    ) -> RunResult:
        """Branch a recorded run after ``at_step`` into a new run and continue it.

        The state after ``at_step`` is rebuilt from the event log alone (the latest checkpoint
        recorded for that step; step 0 of an original run is its goal), without calling the
        provider. The new run starts with a ``run_forked`` lineage event, then copies of the
        source's events up to that point, then a checkpoint of its own starting state, then its
        own steps from ``at_step`` on, with this runner's provider and step budget
        (``SafetyPolicy.max_steps`` counts the inherited steps). The source run is not modified,
        and it does not need to be finished. Usage totals start from the source's totals at the
        fork point (its inherited ``llm_usage`` events); the usage limits recorded there apply,
        each replaced by a limit this runner sets.

        Every check in :func:`multi_bot_agentic.fork.plan_fork` runs before anything is written.

        Args:
            source_run_id: Run to branch from.
            at_step: Step to branch after (``0`` starts over from the goal).
            new_run_id: Run id of the fork; it must not exist yet.
            goal: New goal; the provider answers it before acting on earlier directives.
            bot_id: Registered bot to continue as. The switch is recorded as a handoff, so
                the first new step is a model call under that bot's scope.
            output_schema: New output schema; by default the fork keeps the source's contract.
            output_retries: New correction-round budget (inherited failed answers count).
            reset_usage_limits: Drop the usage limits recorded at the fork point, so only this
                runner's apply.

        Returns:
            Final result of the fork.

        Raises:
            ForkError: If the fork is not allowed; nothing has been written.
            RunBusyError: If another live process holds ``new_run_id``'s lease; nothing has been written.
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
            output_schema=output_schema,
            output_retries=output_retries,
        )
        with self._sole_owner(new_run_id):
            return self._start_fork(new_run_id, plan, reset_usage_limits=reset_usage_limits)

    def _start_fork(self, new_run_id: str, plan: ForkPlan, *, reset_usage_limits: bool) -> RunResult:
        """Write a planned fork's first events and run it, while holding its lease."""

        self.event_log.append(new_run_id, RunState.CREATED, EventType.RUN_FORKED, dict(plan.lineage))
        for event in plan.point.prefix:
            self.event_log.append(new_run_id, RunState(event.state), EventType(event.event_type), event.payload)
        if plan.handoff is not None:
            self.event_log.append(new_run_id, RunState.CREATED, EventType.ACTION_RESULT, dict(plan.handoff))
        self._usage, limits = fork_usage(plan, self.safety_policy.usage_limits, reset=reset_usage_limits)
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
            usage_limits=limits,
        )
        self.active_bot_id = plan.bot
        self.safety_policy = replace(
            self.safety_policy,
            allowed_tools=plan.allowed_tools,
            require_approval=frozenset(plan.require_approval),
            usage_limits=limits,
        )
        self._contract = plan.output_contract
        self._output_failures = (
            failed_attempts(plan.point.prefix, self._contract.schema.sha256) if self._contract else 0
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
                if decision.action == "call_llm":
                    # Checked before the decision is recorded, so the stop leaves no half-done step behind.
                    breach = self.safety_policy.usage_limits.check(self._usage, BEFORE_CALL)
                    if breach is not None:
                        return self._stop_for_usage(run_id, state_machine, goal, observations, step, breach)
                self.event_log.append(
                    run_id,
                    state_machine.state,
                    EventType.DECISION,
                    decision.to_dict(),
                )

                if decision.action == "finish":
                    if self._contract is None:
                        return self._succeed(run_id, state_machine, step + 1, decision)
                    checked = self._check_final_answer(
                        run_id, state_machine, goal, observations, decision, step, self._contract
                    )
                    if isinstance(checked, RunResult):
                        return checked
                    # Another round: the validation errors are the next observation.
                    observations = checked
                    continue
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
                if decision.action == "call_llm":
                    breach = self.safety_policy.usage_limits.check(self._usage, AFTER_CALL)
                    if breach is not None:
                        # The stop's checkpoint closes this step, in the same transaction as the stop.
                        return self._stop_for_usage(run_id, state_machine, goal, observations, step + 1, breach)
                save_checkpoint(
                    self.event_log,
                    run_id=run_id,
                    goal=goal,
                    step=step + 1,
                    state=state_machine.state,
                    observations=observations,
                    active_bot_id=self.active_bot_id,
                    require_approval=self.safety_policy.require_approval,
                    usage_limits=self.safety_policy.usage_limits,
                )

        except (InvalidTransitionError, SafetyError, OSError, RuntimeError, ValueError) as error:
            return self._fail(run_id, state_machine, self.safety_policy.max_steps, str(error))

        return self._fail(run_id, state_machine, self.safety_policy.max_steps, "step budget exhausted")

    @contextmanager
    def _sole_owner(self, run_id: str) -> Iterator[None]:
        """Hold ``run_id``'s lease while continuing it, so no other process continues it at the same time.

        Raises:
            RunBusyError: If a live process holds the lease; nothing was written.
        """

        lease, acquired = self.event_log.acquire_lease(run_id)
        if not acquired:
            raise RunBusyError(run_id, lease)
        try:
            yield
        finally:
            self.event_log.release_lease(lease)

    def _restore_initial_scope(self) -> None:
        """Return to the constructor's active bot and tool allowlist before a run starts or resumes.

        Handoffs and ``resume`` change ``active_bot_id``, the live allowlist, the approval policy,
        and the usage limits for the current run only. Only ``allowed_tools``, ``require_approval``,
        and ``usage_limits`` are reset, so other policy fields keep their current values.
        """

        self.active_bot_id = self._initial_bot_id
        self.safety_policy = replace(
            self.safety_policy,
            allowed_tools=self._initial_allowed_tools,
            require_approval=self._initial_require_approval,
            usage_limits=self._initial_usage_limits,
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
            usage_limits=self.safety_policy.usage_limits,
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
            usage=self._usage,
        )

    def _resume_interrupt(self, run_id: str, snapshot: CheckpointSnapshot) -> RunResult:
        """Continue a run from the interrupt its latest checkpoint paused at.

        The caller holds the run's lease, and the first write is also an atomic claim (it fails if
        anything happened since the pause), so the approved call never runs twice. A resume that finds
        an earlier claim (by a resume that has since stopped) never executes the call again: it
        continues from the recorded tool result, or refuses when no result was recorded.

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

        Only the lease holder gets here, so that resume is known to have ended (it died or failed)
        rather than to be still running. An approved call whose result was recorded is never executed
        again: the recorded result becomes the observation. Anything else (the call started but
        recorded no result, so its outcome is unknown) is refused without writing.
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
        """Return ``snapshot`` restated with this resume's approval policy and usage limits, or ``None``.

        ``None`` means neither changed. A resume records the restated checkpoint before it advances
        (inside the claim at an interrupt), so ``require_approval`` entries it added and usage limits it
        set or reset survive a crash before its next checkpoint.
        """

        merged = tuple(sorted(self.safety_policy.require_approval))
        limits = self.safety_policy.usage_limits
        if set(merged) == set(snapshot.require_approval) and limits == snapshot.usage_limits:
            return None
        return replace(snapshot, require_approval=merged, usage_limits=limits)

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
            usage_limits=self.safety_policy.usage_limits,
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
            request = ModelRequest(goal=goal, observations=observations, tools=self._visible_tool_specs())
            if self._contract is not None:
                request = replace(request, output_schema=self._contract.schema.value, max_output_chars=MAX_ANSWER_CHARS)
            try:
                output = self.provider.complete(request, timeout_seconds=self.safety_policy.timeout_seconds)
            except BilledCallError as error:
                # The provider reported usage for the failed call: count it before the run fails.
                billed = ModelOutput(
                    provider=self.provider.provider_name,
                    text="",
                    usage=error.usage,
                    model=error.model,
                    cost_usd=error.cost_usd,
                )
                self._record_usage(run_id, state, billed)
                raise
            self._record_usage(run_id, state, output)
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

    def _record_usage(self, run_id: str, state: RunState, output: ModelOutput) -> None:
        """Price one model call, add it to the running totals, and record an ``llm_usage`` event.

        Args:
            run_id: Run identifier.
            state: Current state.
            output: The provider's output, with the usage it reported.
        """

        # The UTC day whose prices applied; payloads hold no wall-clock time, so logs stay deterministic.
        priced_on = _utc_now().date()
        cost = price_call(
            output.usage,
            model=output.model,
            provider_cost=output.cost_usd,
            table=self.price_table,
            on=priced_on,
        )
        self._usage = self._usage.add(output.usage, cost.usd)
        self.event_log.append(
            run_id,
            state,
            EventType.LLM_USAGE,
            {
                "bot": self.active_bot_id,
                "provider": output.provider,
                "model": output.model,
                "usage": output.usage.to_dict() if output.usage is not None else None,
                "cost": cost.to_dict(),
                "priced_at": priced_on.isoformat(),
                "totals": self._usage.to_dict(),
            },
        )

    def _stop_for_usage(
        self,
        run_id: str,
        state_machine: RunStateMachine,
        goal: str,
        observations: tuple[Observation, ...],
        steps: int,
        breach: LimitBreach,
    ) -> RunResult:
        """Stop the run at a usage limit: record the breach and checkpoint, so ``resume`` continues.

        The transition, the ``usage_limit_exceeded`` event, and the checkpoint are one transaction, so
        a process that dies while stopping leaves none of them: ``resume`` then continues from the
        previous checkpoint, where the before-call check stops the run again.

        Args:
            run_id: Run identifier.
            state_machine: Run state machine (``deciding`` before a call, ``acting`` after one).
            goal: User goal.
            observations: Observations to resume with (they include the output of a call that
                exceeded the limit, so it is never repeated).
            steps: Steps completed.
            breach: The limit that was breached.

        Returns:
            Result in state ``usage_limit_exceeded``.
        """

        previous, current = state_machine.transition_to(RunState.USAGE_LIMIT_EXCEEDED)
        step = steps + 1 if breach.phase == BEFORE_CALL else steps
        payload = breach.to_dict() | {
            "step": step,
            "limits": self.safety_policy.usage_limits.to_dict(),
            "totals": self._usage.to_dict(),
        }
        checkpoint = CheckpointSnapshot(
            run_id=run_id,
            goal=goal,
            step=steps,
            state=current,
            observations=observations,
            active_bot_id=self.active_bot_id,
            require_approval=tuple(sorted(self.safety_policy.require_approval)),
            usage_limits=self.safety_policy.usage_limits,
        )
        self.event_log.append_guarded(
            run_id,
            [
                (current, EventType.STATE_TRANSITION, {"from": previous.value, "to": current.value}),
                (current, EventType.USAGE_LIMIT_EXCEEDED, payload),
                (current, EventType.CHECKPOINT, checkpoint.to_payload()),
            ],
        )
        return RunResult(
            run_id=run_id,
            state=state_machine.state,
            answer=f"stopped: {breach.message}",
            steps=steps,
            usage=self._usage,
            usage_limit=breach,
        )

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

    def _check_final_answer(
        self,
        run_id: str,
        state_machine: RunStateMachine,
        goal: str,
        observations: tuple[Observation, ...],
        decision: Decision,
        step: int,
        contract: OutputContract,
    ) -> RunResult | tuple[Observation, ...]:
        """Validate a ``finish`` decision's answer against the run's output contract.

        The run moves to ``validating``. A valid answer is recorded as a ``final_output`` event and
        the run succeeds. An invalid one is recorded as an ``output_validation_failed`` event,
        followed by the checkpoint that holds the correction observation when a round is left, or
        by the end of the run in ``output_invalid``. A round needs a correction budget and two more
        steps: the model's corrected answer and the decision that checks it.

        Each outcome is written in one transaction with what follows from it, so a crash never
        records a check without its checkpoint or end: a resume either checks the same answer
        again, with nothing counted yet, or continues after the recorded outcome.

        Args:
            run_id: Run identifier.
            state_machine: Run state machine (``deciding``).
            goal: User goal.
            observations: Observations the ``finish`` decision used.
            decision: The ``finish`` decision.
            step: Zero-based loop step.
            contract: Output contract of the run.

        Returns:
            The final result, or the observations of the next round (ending with the correction).
        """

        self._transition(run_id, state_machine, RunState.VALIDATING)
        check = check_output(str(decision.payload.get("answer", "")), contract.schema)
        attempt = self._output_failures + 1
        steps = step + 1
        if check.valid:
            output = FinalOutput(
                value=check.value,
                attempt=attempt,
                source=check.source or "answer",
                output_sha256=sha256_of(check.value),
                output_bytes=check.output_bytes,
                schema_sha256=contract.schema.sha256,
            )
            answer = str(decision.payload.get("answer", ""))
            self._finish_validating(
                run_id,
                state_machine,
                (RunState.VALIDATING, EventType.FINAL_OUTPUT, output.to_payload()),
                (RunState.SUCCEEDED, EventType.RUN_COMPLETED, {"answer": answer, "steps": steps}),
            )
            return RunResult(
                run_id=run_id, state=state_machine.state, answer=answer, steps=steps, output=output, usage=self._usage
            )
        self._output_failures = attempt
        rounds_left = attempt <= contract.retries
        steps_left = self.safety_policy.max_steps - steps >= 2
        failure: dict[str, Any] = {
            "attempt": attempt,
            "max_attempts": contract.max_attempts,
            "errors": list(check.errors),
            "schema_sha256": contract.schema.sha256,
            "retry": rounds_left and steps_left,
        }
        if not rounds_left:
            failure["stop"] = "retries_exhausted"
        elif not steps_left:
            failure["stop"] = "step_budget"
        if rounds_left and steps_left:
            correction = Observation(
                source=CORRECTION_SOURCE,
                content=correction_text(check.errors, attempt=attempt, contract=contract),
                metadata={"attempt": attempt, "schema_sha256": contract.schema.sha256},
            )
            next_observations = (*observations, correction)
            checkpoint = CheckpointSnapshot(
                run_id=run_id,
                goal=goal,
                step=steps,
                state=RunState.VALIDATING,
                observations=next_observations,
                active_bot_id=self.active_bot_id,
                require_approval=tuple(sorted(self.safety_policy.require_approval)),
            )
            self.event_log.append_guarded(
                run_id,
                [
                    (RunState.VALIDATING, EventType.OUTPUT_VALIDATION_FAILED, failure),
                    (RunState.VALIDATING, EventType.CHECKPOINT, checkpoint.to_payload()),
                ],
            )
            return next_observations
        # The reason is exported in traces, so it never quotes the answer; the errors are in the event.
        if not rounds_left:
            count = len(check.errors)
            reason = (
                f"the final answer failed output validation after {attempt} attempt{'' if attempt == 1 else 's'} "
                f"({count} error{'' if count == 1 else 's'} in the last answer)"
            )
        else:
            reason = (
                "the final answer failed output validation and no steps are left for a correction round "
                "(raise --max-steps)"
            )
        self._finish_validating(
            run_id,
            state_machine,
            (RunState.VALIDATING, EventType.OUTPUT_VALIDATION_FAILED, failure),
            (RunState.OUTPUT_INVALID, EventType.RUN_FAILED, {"reason": reason, "steps": steps}),
        )
        return RunResult(
            run_id=run_id,
            state=state_machine.state,
            answer=reason,
            steps=steps,
            output_errors=check.errors,
            usage=self._usage,
        )

    def _finish_validating(
        self,
        run_id: str,
        state_machine: RunStateMachine,
        check: tuple[RunState, EventType, dict[str, Any]],
        end: tuple[RunState, EventType, dict[str, Any]],
    ) -> None:
        """End a run from ``validating`` in one transaction: the check's event, the transition, the end.

        The state machine moves to the terminal state of ``end`` only after the write succeeded.
        """

        final_state = end[0]
        transition = {"from": state_machine.state.value, "to": final_state.value}
        self.event_log.append_guarded(run_id, [check, (final_state, EventType.STATE_TRANSITION, transition), end])
        state_machine.transition_to(final_state)

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
        return RunResult(run_id=run_id, state=state_machine.state, answer=answer, steps=steps, usage=self._usage)

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
        return RunResult(run_id=run_id, state=state_machine.state, answer=reason, steps=steps, usage=self._usage)

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
        return RunResult(run_id=run_id, state=state_machine.state, answer=reason, steps=steps, usage=self._usage)


def fork_usage(plan: ForkPlan, configured: UsageLimits, *, reset: bool = False) -> tuple[UsageTotals, UsageLimits]:
    """Return the usage totals a fork starts from and the usage limits it runs with.

    Args:
        plan: The fork plan.
        configured: Limits set for the fork; each replaces the one recorded at the fork point.
        reset: Drop the recorded limits, so only ``configured`` applies.

    Returns:
        The totals of the inherited ``llm_usage`` events and the effective limits.
    """

    recorded = UsageLimits() if reset else UsageLimits.from_dict(plan.point.event.payload.get("usage_limits"))
    return UsageTotals.from_events(plan.point.prefix), recorded.override(configured)


def _stop_phase(events: Sequence[EventRecord]) -> str:
    """Return the phase (``before_call`` or ``after_call``) of the run's latest usage-limit stop."""

    for event in reversed(events):
        if event.event_type == EventType.USAGE_LIMIT_EXCEEDED.value:
            return AFTER_CALL if event.payload.get("phase") == AFTER_CALL else BEFORE_CALL
    return BEFORE_CALL


def _utc_now() -> datetime:
    """Return the current UTC time; its date selects effective-dated prices (``priced_at``)."""

    return datetime.now(timezone.utc)


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
