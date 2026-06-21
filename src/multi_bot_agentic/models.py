"""Typed data models shared across the agent runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal
from uuid import uuid4


class RunState(str, Enum):
    """Lifecycle states for one agent run."""

    CREATED = "created"
    OBSERVING = "observing"
    DECIDING = "deciding"
    ACTING = "acting"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EventType(str, Enum):
    """Durable event categories emitted by the runtime."""

    RUN_CREATED = "run_created"
    STATE_TRANSITION = "state_transition"
    OBSERVATION = "observation"
    DECISION = "decision"
    ACTION_REQUESTED = "action_requested"
    ACTION_RESULT = "action_result"
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"
    RUN_CANCELLED = "run_cancelled"


DecisionAction = Literal["call_llm", "call_tool", "finish", "fail", "cancel"]


@dataclass(frozen=True)
class Observation:
    """Fact observed by the runner before deterministic decision-making.

    Attributes:
        observation_id: Stable identifier for rationale references.
        source: Source category, such as user, model, tool, or system.
        content: Human-readable observation text.
        metadata: Structured metadata that is safe to persist.
    """

    source: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    observation_id: str = field(default_factory=lambda: str(uuid4()))

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation.

        Returns:
            Dictionary representation of the observation.
        """

        return {
            "observation_id": self.observation_id,
            "source": self.source,
            "content": self.content,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class RationaleTrace:
    """Deterministic explanation for a decision.

    Attributes:
        rule_id: Rule that selected the final action.
        observations_used: Observation identifiers used by the rule.
        rejected_actions: Candidate actions rejected by the engine.
        explanation: Human-readable rationale.
    """

    rule_id: str
    observations_used: tuple[str, ...]
    rejected_actions: tuple[str, ...]
    explanation: str

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation.

        Returns:
            Dictionary representation of the rationale trace.
        """

        return {
            "rule_id": self.rule_id,
            "observations_used": list(self.observations_used),
            "rejected_actions": list(self.rejected_actions),
            "explanation": self.explanation,
        }


@dataclass(frozen=True)
class Decision:
    """Action selected by the deterministic decision engine.

    Attributes:
        action: Next action type.
        target: Optional provider or tool target.
        payload: Action-specific payload.
        rationale: Deterministic rationale trace.
    """

    action: DecisionAction
    target: str | None
    payload: dict[str, Any]
    rationale: RationaleTrace

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation.

        Returns:
            Dictionary representation of the decision.
        """

        return {
            "action": self.action,
            "target": self.target,
            "payload": self.payload,
            "rationale": self.rationale.to_dict(),
        }


@dataclass(frozen=True)
class ModelRequest:
    """Normalized provider request.

    Attributes:
        goal: User goal.
        observations: Observed facts to include as context.
        max_output_chars: Provider output bound.
    """

    goal: str
    observations: tuple[Observation, ...]
    max_output_chars: int = 2000


@dataclass(frozen=True)
class ModelOutput:
    """Normalized provider output consumed by the runner.

    Attributes:
        provider: Provider name.
        text: Model response text.
        raw: Non-secret provider metadata.
    """

    provider: str
    text: str
    raw: dict[str, Any] = field(default_factory=dict)

    def to_observation(self) -> Observation:
        """Convert model output into an observation.

        Returns:
            Observation representing the model output.
        """

        return Observation(source=f"llm:{self.provider}", content=self.text, metadata=self.raw)


@dataclass(frozen=True)
class ToolInvocation:
    """Tool invocation selected by the decision engine.

    Attributes:
        tool_name: Registered tool name.
        arguments: Tool arguments.
    """

    tool_name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ToolResult:
    """Result returned by a tool adapter.

    Attributes:
        tool_name: Tool name.
        ok: Whether execution succeeded.
        content: Human-readable result.
        metadata: Structured metadata that is safe to persist.
    """

    tool_name: str
    ok: bool
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_observation(self) -> Observation:
        """Convert tool result into an observation.

        Returns:
            Observation representing the tool result.
        """

        return Observation(source=f"tool:{self.tool_name}", content=self.content, metadata=self.metadata)
