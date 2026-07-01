"""Observe -> Decide -> Act runner."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from multi_bot_agentic.decision import DeterministicDecisionEngine
from multi_bot_agentic.event_log import SQLiteEventLog
from multi_bot_agentic.lifecycle import InvalidTransitionError, RunStateMachine
from multi_bot_agentic.llm.base import LLMAdapter
from multi_bot_agentic.models import (
    Decision,
    EventType,
    ModelRequest,
    Observation,
    RunState,
    ToolInvocation,
)
from multi_bot_agentic.safety import SafetyError, SafetyPolicy
from multi_bot_agentic.tools.base import ToolAdapter


@dataclass(frozen=True)
class RunResult:
    """Final run result."""

    run_id: str
    state: RunState
    answer: str
    steps: int


class AgentRunner:
    """Runs an auditable Observe -> Decide -> Act loop."""

    def __init__(
        self,
        provider: LLMAdapter,
        event_log: SQLiteEventLog,
        tools: dict[str, ToolAdapter],
        safety_policy: SafetyPolicy,
    ) -> None:
        """Initialize the runner.

        Args:
            provider: LLM provider adapter.
            event_log: Durable event log.
            tools: Registered tool adapters by name.
            safety_policy: Runtime safety controls.
        """

        self.provider = provider
        self.event_log = event_log
        self.tools = tools
        self.safety_policy = safety_policy
        self.decision_engine = DeterministicDecisionEngine(provider_name=provider.provider_name)

    def run(self, goal: str, run_id: str | None = None) -> RunResult:
        """Execute one bounded agent run.

        Args:
            goal: User goal.
            run_id: Optional run identifier.

        Returns:
            Final run result.
        """

        self.safety_policy.validate_goal(goal)
        selected_run_id = run_id or str(uuid4())
        state_machine = RunStateMachine()
        observations: tuple[Observation, ...] = (Observation(source="user", content=goal),)
        self.event_log.append(
            selected_run_id,
            state_machine.state,
            EventType.RUN_CREATED,
            {"goal": goal, "provider": self.provider.provider_name},
        )

        try:
            for step in range(self.safety_policy.max_steps):
                self.safety_policy.validate_step(step)
                if self.safety_policy.is_cancelled():
                    return self._cancel(selected_run_id, state_machine, step, "cancellation requested")

                self._transition(selected_run_id, state_machine, RunState.OBSERVING)
                for observation in observations:
                    self.event_log.append(
                        selected_run_id,
                        state_machine.state,
                        EventType.OBSERVATION,
                        observation.to_dict(),
                    )

                self._transition(selected_run_id, state_machine, RunState.DECIDING)
                decision = self.decision_engine.decide(observations, step, self.safety_policy)
                self.event_log.append(
                    selected_run_id,
                    state_machine.state,
                    EventType.DECISION,
                    decision.to_dict(),
                )

                if decision.action == "finish":
                    return self._succeed(selected_run_id, state_machine, step + 1, decision)
                if decision.action == "cancel":
                    return self._cancel(
                        selected_run_id,
                        state_machine,
                        step + 1,
                        str(decision.payload.get("reason", "cancelled")),
                    )
                if decision.action == "fail":
                    return self._fail(
                        selected_run_id,
                        state_machine,
                        step + 1,
                        str(decision.payload.get("reason", "failed")),
                    )

                self._transition(selected_run_id, state_machine, RunState.ACTING)
                new_observation = self._act(selected_run_id, state_machine.state, goal, observations, decision)
                observations = (*observations, new_observation)

        except (InvalidTransitionError, SafetyError, OSError, RuntimeError, ValueError) as error:
            return self._fail(selected_run_id, state_machine, self.safety_policy.max_steps, str(error))

        return self._fail(selected_run_id, state_machine, self.safety_policy.max_steps, "step budget exhausted")

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
                ModelRequest(goal=goal, observations=observations),
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
            if decision.target is None:
                raise ValueError("tool decision requires a target")
            self.safety_policy.validate_tool(decision.target)
            tool = self.tools.get(decision.target)
            if tool is None:
                raise ValueError(f"tool is not registered: {decision.target}")
            result = tool.execute(ToolInvocation(tool_name=decision.target, arguments=decision.payload))
            self.event_log.append(
                run_id,
                state,
                EventType.ACTION_RESULT,
                {
                    "kind": "tool",
                    "tool": result.tool_name,
                    "ok": result.ok,
                    "content": result.content,
                    "metadata": result.metadata,
                },
            )
            return result.to_observation()

        raise ValueError(f"unsupported action for _act: {decision.action}")

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


def build_default_tools(root: Path) -> dict[str, ToolAdapter]:
    """Build default allowlisted tools.

    Args:
        root: Root directory for read-only file access.

    Returns:
        Tool registry.
    """

    from multi_bot_agentic.tools.checklist import ChecklistTool
    from multi_bot_agentic.tools.echo import EchoTool
    from multi_bot_agentic.tools.filesystem_readonly import ReadOnlyFileTool

    return {
        "checklist": ChecklistTool(),
        "echo": EchoTool(),
        "readonly_file": ReadOnlyFileTool(root=root),
    }
