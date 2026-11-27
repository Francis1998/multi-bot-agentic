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
    AWAITING_APPROVAL = "awaiting_approval"
    USAGE_LIMIT_EXCEEDED = "usage_limit_exceeded"
    ACTING = "acting"
    VALIDATING = "validating"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    OUTPUT_INVALID = "output_invalid"


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
    CHECKPOINT = "checkpoint"
    RUN_FORKED = "run_forked"
    INTERRUPT = "interrupt"
    APPROVAL_DECISION = "approval_decision"
    OUTPUT_VALIDATION_FAILED = "output_validation_failed"
    FINAL_OUTPUT = "final_output"
    LLM_USAGE = "llm_usage"
    USAGE_LIMIT_EXCEEDED = "usage_limit_exceeded"


DecisionAction = Literal["call_llm", "call_tool", "handoff", "finish", "fail", "cancel"]


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
class ToolSpec:
    """Model-facing description of a callable tool.

    Attributes:
        name: Registered tool name used in ``TOOL:<name>:<payload>`` directives.
        description: Human-readable purpose of the tool.
        input_schema: JSON Schema object describing the tool arguments.
    """

    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)

    def signature(self, max_chars: int = 400) -> str:
        """Summarize the top-level arguments declared by ``input_schema``.

        Schemas may come from untrusted MCP servers, so malformed entries are
        tolerated and the summary is bounded to keep prompts small.

        Args:
            max_chars: Maximum length of the returned summary.

        Returns:
            Text such as ``query: string (required), limit: integer``, or an
            empty string when the schema declares no properties.
        """

        properties = self.input_schema.get("properties")
        if not isinstance(properties, dict) or not properties:
            return ""
        raw_required = self.input_schema.get("required")
        required = {item for item in raw_required if isinstance(item, str)} if isinstance(raw_required, list) else set()
        parts: list[str] = []
        for key, schema in properties.items():
            declared = schema.get("type", "any") if isinstance(schema, dict) else "any"
            type_name = "|".join(str(item) for item in declared) if isinstance(declared, list) else str(declared)
            parts.append(f"{key}: {type_name}{' (required)' if key in required else ''}")
        summary = ", ".join(parts)
        return summary if len(summary) <= max_chars else summary[: max_chars - 1] + "…"


@dataclass(frozen=True)
class ModelRequest:
    """Normalized provider request.

    Attributes:
        goal: User goal.
        observations: Observed facts to include as context.
        max_output_chars: Provider output bound.
        tools: Optional tool catalog advertised to the model (empty keeps prompts unchanged).
        output_schema: JSON Schema the final answer must validate against (``run --output-schema``);
            ``None`` keeps prompts unchanged.
    """

    goal: str
    observations: tuple[Observation, ...]
    max_output_chars: int = 2000
    tools: tuple[ToolSpec, ...] = ()
    output_schema: dict[str, Any] | bool | None = None


# Token counters of :class:`Usage`, in report order.
TOKEN_FIELDS = ("input_tokens", "output_tokens", "cached_input_tokens", "reasoning_tokens", "total_tokens")


@dataclass(frozen=True)
class Usage:
    """Token usage one model call reported, normalized across providers.

    A counter the provider did not report stays ``None`` (unknown), never ``0``. Following the
    OpenTelemetry GenAI conventions, ``input_tokens`` includes cached input tokens and
    ``output_tokens`` includes reasoning (thinking) tokens.

    Attributes:
        requests: Model requests this usage covers (``1`` for one call).
        input_tokens: All input (prompt) tokens, cached ones included.
        output_tokens: All output tokens, reasoning tokens included.
        cached_input_tokens: Input tokens served from a provider cache (part of ``input_tokens``).
        reasoning_tokens: Output tokens spent on reasoning (part of ``output_tokens``).
        total_tokens: Provider-reported total, else ``input_tokens + output_tokens``.
    """

    requests: int = 1
    input_tokens: int | None = None
    output_tokens: int | None = None
    cached_input_tokens: int | None = None
    reasoning_tokens: int | None = None
    total_tokens: int | None = None

    @property
    def measured(self) -> bool:
        """Return whether the provider reported both input and output tokens."""

        return self.input_tokens is not None and self.output_tokens is not None

    def to_dict(self) -> dict[str, int | None]:
        """Return a JSON-serializable representation (unknown counters are ``None``)."""

        return {"requests": self.requests, **{name: getattr(self, name) for name in TOKEN_FIELDS}}

    @classmethod
    def from_dict(cls, payload: Any) -> Usage:
        """Rebuild usage recorded by :meth:`to_dict`; malformed counters become unknown."""

        data = payload if isinstance(payload, dict) else {}
        requests = _count(data.get("requests"))
        counts = {name: _count(data.get(name)) for name in TOKEN_FIELDS}
        return cls(requests=1 if requests is None else requests, **counts)


def _count(value: Any) -> int | None:
    """Return ``value`` when it is a non-negative integer token count, else ``None``."""

    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


@dataclass(frozen=True)
class ModelOutput:
    """Normalized provider output consumed by the runner.

    Attributes:
        provider: Provider name.
        text: Model response text.
        raw: Non-secret provider metadata.
        usage: Token usage the provider reported for the call, or ``None`` when it reported none.
        model: Model id the call is priced as, if the adapter knows it.
        cost_usd: Cost the provider itself reported for the call (Claude Code), if any.
    """

    provider: str
    text: str
    raw: dict[str, Any] = field(default_factory=dict)
    usage: Usage | None = None
    model: str | None = None
    cost_usd: float | None = None

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
