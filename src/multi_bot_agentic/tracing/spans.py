"""Build a deterministic OpenTelemetry GenAI span tree from a run's event records.

Span shapes follow the OpenTelemetry GenAI semantic conventions (Development status,
``open-telemetry/semantic-conventions-genai`` at commit ``e6658f14c9``, 2026-11-06):

* one root ``invoke_agent`` span (kind ``INTERNAL``) for the orchestrated run;
* an ``invoke_agent {bot}`` child span for each stretch of the run a registered bot was active;
* a ``chat {model}`` (``generate_content`` for Gemini) span for every provider call;
* an ``execute_tool {tool}`` span for every built-in or MCP tool call;
* span events for handoffs, approvals, checkpoints, resumes, fork points, and the terminal decision;
* for a forked run, a span link from the root span to the parent run's root span.

Timestamps come from the event log. An action span starts at its ``action_requested`` event
and ends at its ``action_result`` event; an action without a result ends at the next recorded
event. Trace and span ids are SHA-256 digests of the run id and a per-span key (derived from
event sequence numbers), so exporting the same run always yields byte-identical output.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Final

from multi_bot_agentic.event_log import EventRecord
from multi_bot_agentic.tracing.privacy import MAX_ERROR_CHARS, redact_text, redact_value, to_json_object
from multi_bot_agentic.tracing.timeline import (
    Approval,
    Checkpoint,
    DecisionRef,
    FinalDecision,
    Fork,
    Handoff,
    ModelCall,
    ObservationRef,
    Resume,
    RunTimeline,
    ToolCall,
    nanos_between,
    parse_run,
    timestamp_to_unix_nanos,
)

# Adapter name -> well-known ``gen_ai.provider.name`` value. Other adapters (``fake``) use
# their own name as a custom value, which the conventions allow.
PROVIDER_NAMES: Final[Mapping[str, str]] = {
    "openai": "openai",
    "kimi": "moonshot_ai",
    "gemini": "gcp.gemini",
    "claude_code": "anthropic",
}
# Adapters whose API maps to a different well-known ``gen_ai.operation.name`` than ``chat``.
OPERATION_NAMES: Final[Mapping[str, str]] = {"gemini": "generate_content"}
# Adapters that run in-process; their inference spans use kind INTERNAL instead of CLIENT.
IN_PROCESS_PROVIDERS: Final[frozenset[str]] = frozenset({"fake"})
# Prefix of attributes and events that have no GenAI semantic-convention equivalent.
NAMESPACE: Final[str] = "multi_bot_agentic"
OTHER_ERROR: Final[str] = "_OTHER"

_HTTP_ERROR = re.compile(r"\bHTTP Error (\d{3})\b")


class SpanKind(IntEnum):
    """OTLP ``Span.SpanKind`` values."""

    INTERNAL = 1
    SERVER = 2
    CLIENT = 3
    PRODUCER = 4
    CONSUMER = 5


class StatusCode(IntEnum):
    """OTLP ``Status.StatusCode`` values."""

    UNSET = 0
    OK = 1
    ERROR = 2


@dataclass(frozen=True)
class SpanEvent:
    """A timestamped span event.

    Attributes:
        name: Event name.
        time_unix_nano: Event time in Unix nanoseconds.
        attributes: Event attributes.
    """

    name: str
    time_unix_nano: int
    attributes: Mapping[str, Any]


@dataclass(frozen=True)
class SpanLink:
    """A link from a span to a span of another (or the same) trace.

    Attributes:
        trace_id: 32-hex-digit trace id of the linked span.
        span_id: 16-hex-digit span id of the linked span.
        attributes: Link attributes.
    """

    trace_id: str
    span_id: str
    attributes: Mapping[str, Any]


@dataclass(frozen=True)
class Span:
    """One exported span.

    Attributes:
        span_id: 16-hex-digit span id.
        parent_span_id: Parent span id, or ``None`` for the root span.
        name: Span name.
        kind: Span kind.
        start_time_unix_nano: Start time in Unix nanoseconds.
        end_time_unix_nano: End time in Unix nanoseconds.
        attributes: Span attributes (insertion order is preserved in exports).
        events: Span events in time order.
        status_code: Span status code.
        status_message: Status description (only set for errors).
        links: Links to causally related spans (a fork's root links to its parent run's root).
    """

    span_id: str
    parent_span_id: str | None
    name: str
    kind: SpanKind
    start_time_unix_nano: int
    end_time_unix_nano: int
    attributes: Mapping[str, Any]
    events: tuple[SpanEvent, ...] = ()
    status_code: StatusCode = StatusCode.UNSET
    status_message: str = ""
    links: tuple[SpanLink, ...] = ()


@dataclass(frozen=True)
class Trace:
    """A run exported as one trace.

    Attributes:
        run_id: Run identifier.
        trace_id: 32-hex-digit trace id.
        spans: Spans, root first, then in event order.
    """

    run_id: str
    trace_id: str
    spans: tuple[Span, ...]

    @property
    def root(self) -> Span:
        """Return the root ``invoke_agent`` span."""

        return self.spans[0]


def trace_id_for(run_id: str) -> str:
    """Return the deterministic 128-bit trace id (32 hex digits) of a run.

    Args:
        run_id: Run identifier.

    Returns:
        Lower-case hex trace id.
    """

    return _hex_id("trace", run_id, digits=32)


def span_id_for(run_id: str, key: str) -> str:
    """Return a deterministic 64-bit span id (16 hex digits).

    Args:
        run_id: Run identifier.
        key: Per-span key, for example ``root`` or ``seq:7``.

    Returns:
        Lower-case hex span id.
    """

    return _hex_id("span", run_id, key, digits=16)


def build_trace(
    events: Sequence[EventRecord],
    *,
    include_content: bool = False,
    agent_name: str | None = None,
) -> Trace:
    """Convert one run's event records into an OpenTelemetry GenAI span tree.

    Args:
        events: Every event of exactly one run.
        include_content: Record the goal, reconstructed model inputs, model outputs, tool
            arguments, tool results, and handoff summaries (redacted). Off by default because
            the semantic conventions treat them as sensitive, opt-in content.
        agent_name: Optional ``gen_ai.agent.name`` for the root span. The conventions say not to
            invent one, so the root span is named ``invoke_agent`` when it is omitted.

    Returns:
        The trace.

    Raises:
        TraceInputError: If the events are empty, mix runs, or carry invalid timestamps.
    """

    return _TraceBuilder(parse_run(events), include_content=include_content, agent_name=agent_name).build()


def provider_attributes(provider: str) -> tuple[str, str, SpanKind]:
    """Map an adapter name to its ``gen_ai.provider.name``, operation name, and span kind.

    Args:
        provider: Adapter name (``openai``, ``gemini``, ``claude_code``, ``kimi``, ``fake``, ...).

    Returns:
        Provider name, operation name, and span kind.
    """

    return (
        PROVIDER_NAMES.get(provider, provider),
        OPERATION_NAMES.get(provider, "chat"),
        SpanKind.INTERNAL if provider in IN_PROCESS_PROVIDERS else SpanKind.CLIENT,
    )


def classify_failure(reason: str) -> str:
    """Return a low-cardinality ``error.type`` for a free-text failure reason.

    Args:
        reason: Failure reason recorded by the runner.

    Returns:
        The HTTP status code for ``HTTP Error NNN`` reasons, ``timeout`` for timeouts,
        ``step_budget_exhausted`` when the run ran out of steps, otherwise ``_OTHER``.
    """

    if reason == "step budget exhausted":
        return "step_budget_exhausted"
    match = _HTTP_ERROR.search(reason)
    if match is not None:
        return match.group(1)
    if "timed out" in reason.lower():
        return "timeout"
    return OTHER_ERROR


def model_directive(output: str) -> tuple[str, str | None]:
    """Classify a model output the way the decision engine reads it.

    Args:
        output: Model output text.

    Returns:
        ``(kind, target)``: ``("tool", name)``, ``("handoff", bot)``, ``("done", None)``, or
        ``("text", None)``.
    """

    if output.startswith("TOOL:"):
        return "tool", output.split(":", 2)[1].strip() or None
    if output.startswith("HANDOFF:"):
        return "handoff", output.split(":", 2)[1].strip() or None
    if output.startswith("DONE:"):
        return "done", None
    return "text", None


def tool_error_type(call: ToolCall) -> str | None:
    """Return the ``error.type`` of a failed tool call, or ``None`` when it succeeded.

    MCP failures report the JSON-RPC error code when there is one, otherwise the bridge's
    ``error_kind`` (``tool_error`` for ``isError`` results, ``timeout``, ``transport_error``,
    ``invalid_arguments``, ``protocol_error``); other failed tools report ``tool_error``.

    Args:
        call: Tool call.

    Returns:
        Error type or ``None``.
    """

    if call.ok is None:
        if call.interrupted:
            return "interrupted"
        return classify_failure(call.failure) if call.failure is not None else None
    if call.ok:
        return None
    error_code = call.metadata.get("error_code")
    if isinstance(error_code, int) and not isinstance(error_code, bool):
        return str(error_code)
    error_kind = call.metadata.get("error_kind")
    return error_kind if isinstance(error_kind, str) and error_kind else "tool_error"


def mcp_identity(call: ToolCall) -> tuple[str, str] | None:
    """Return ``(server, remote tool)`` for an MCP tool call, or ``None`` for a built-in tool."""

    server, remote = call.metadata.get("mcp_server"), call.metadata.get("mcp_tool")
    if isinstance(server, str) and isinstance(remote, str):
        return server, remote
    if call.tool.startswith("mcp__") and "__" in call.tool[5:]:
        server, remote = call.tool[5:].split("__", 1)
        return server, remote
    return None


def run_error_type(timeline: RunTimeline) -> str | None:
    """Return the ``error.type`` of a failed run, or ``None`` when it did not fail.

    Args:
        timeline: Run timeline.

    Returns:
        The failing rule id for ``fail`` decisions, otherwise :func:`classify_failure` of the reason.
    """

    outcome = timeline.outcome
    if outcome is None or outcome.state != "failed":
        return None
    final = timeline.final_decision
    if final is not None and final.action == "fail" and final.rule_id and final.seq < outcome.seq:
        return final.rule_id
    return classify_failure(outcome.reason or "")


@dataclass
class _SpanDraft:
    """Mutable span used while the tree is assembled."""

    span_id: str
    parent_span_id: str | None
    name: str
    kind: SpanKind
    start: int
    end: int
    order: int
    attributes: dict[str, Any]
    events: list[SpanEvent] = field(default_factory=list)
    status_code: StatusCode = StatusCode.UNSET
    status_message: str = ""
    links: list[SpanLink] = field(default_factory=list)

    def fail(self, error_type: str, message: str) -> None:
        """Mark the span as failed."""

        self.attributes["error.type"] = error_type
        self.status_code = StatusCode.ERROR
        self.status_message = redact_text(message, MAX_ERROR_CHARS)

    def freeze(self) -> Span:
        """Return the immutable span."""

        return Span(
            span_id=self.span_id,
            parent_span_id=self.parent_span_id,
            name=self.name,
            kind=self.kind,
            start_time_unix_nano=self.start,
            end_time_unix_nano=max(self.start, self.end),
            attributes=dict(self.attributes),
            events=tuple(self.events),
            status_code=self.status_code,
            status_message=self.status_message,
            links=tuple(self.links),
        )


class _TraceBuilder:
    """Turns a :class:`RunTimeline` into spans."""

    def __init__(self, timeline: RunTimeline, *, include_content: bool, agent_name: str | None) -> None:
        self.timeline = timeline
        self.include_content = include_content
        self.agent_name = agent_name.strip() if agent_name and agent_name.strip() else None
        self.run_id = timeline.run_id
        self.drafts: list[_SpanDraft] = []

    def build(self) -> Trace:
        """Assemble the root span, bot spans, action spans, and span events."""

        timeline = self.timeline
        run_start, run_end = nanos_between(timeline.started_at, timeline.ended_at)
        root = self._root(run_start, run_end)
        agent_span = root
        if timeline.initial_bot is not None:
            agent_span = self._bot_span(timeline.initial_bot, start=run_start, order=timeline.first_seq, allowed=())
        for step in timeline.steps:
            if isinstance(step, ModelCall):
                self._model_span(step, agent_span)
            elif isinstance(step, ToolCall):
                self._tool_span(step, agent_span)
            elif isinstance(step, Handoff):
                agent_span = self._handoff(step, agent_span, root)
            elif isinstance(step, Approval):
                agent_span.events.append(self._approval_event(step))
            elif isinstance(step, FinalDecision):
                root.events.append(self._decision_event(step.decision))
            elif isinstance(step, Checkpoint):
                root.events.append(self._checkpoint_event(step))
            elif isinstance(step, Resume):
                root.events.append(SpanEvent(f"{NAMESPACE}.run.resumed", timestamp_to_unix_nanos(step.at), {}))
            elif isinstance(step, Fork):
                root.events.append(self._fork_event(step))
        if agent_span is not root:
            agent_span.end = run_end
        spans = [root.freeze()] + [
            draft.freeze() for draft in sorted(self.drafts[1:], key=lambda item: (item.order, item.span_id))
        ]
        return Trace(run_id=self.run_id, trace_id=trace_id_for(self.run_id), spans=tuple(spans))

    def _root(self, start: int, end: int) -> _SpanDraft:
        """Create the root ``invoke_agent`` span."""

        timeline = self.timeline
        attributes: dict[str, Any] = {"gen_ai.operation.name": "invoke_agent"}
        if self.agent_name is not None:
            attributes["gen_ai.agent.name"] = self.agent_name
        attributes["gen_ai.conversation.id"] = self.run_id
        models = sorted({model for model in (_model_of(call) for call in self._model_calls()) if model})
        if len(models) == 1:
            attributes["gen_ai.request.model"] = models[0]
        usages = [_usage(call.metadata) for call in self._model_calls() if call.output is not None]
        if usages and all(
            input_tokens is not None and output_tokens is not None for input_tokens, output_tokens in usages
        ):
            attributes["gen_ai.usage.input_tokens"] = sum(item[0] or 0 for item in usages)
            attributes["gen_ai.usage.output_tokens"] = sum(item[1] or 0 for item in usages)
        attributes[f"{NAMESPACE}.run.state"] = timeline.final_state
        if timeline.outcome is not None and timeline.outcome.steps is not None:
            attributes[f"{NAMESPACE}.run.steps"] = timeline.outcome.steps
        if timeline.provider is not None:
            attributes[f"{NAMESPACE}.run.provider"] = timeline.provider
        attributes[f"{NAMESPACE}.run.event_count"] = timeline.event_count
        resumes = sum(1 for step in timeline.steps if isinstance(step, Resume))
        if resumes:
            attributes[f"{NAMESPACE}.run.resume_count"] = resumes
        fork = timeline.fork
        if fork is not None:
            attributes[f"{NAMESPACE}.fork.parent_run_id"] = fork.parent_run_id
            attributes[f"{NAMESPACE}.fork.step"] = fork.fork_step
            attributes[f"{NAMESPACE}.fork.inherited_events"] = fork.inherited_events
            if fork.overrides:
                attributes[f"{NAMESPACE}.fork.overrides"] = list(fork.overrides)
        if self.include_content:
            if timeline.goal is not None:
                attributes["gen_ai.input.messages"] = [_text_message("user", timeline.goal)]
            if timeline.outcome is not None and timeline.outcome.answer is not None:
                attributes["gen_ai.output.messages"] = [_text_message("assistant", timeline.outcome.answer)]
        name = "invoke_agent" if self.agent_name is None else f"invoke_agent {self.agent_name}"
        root = self._draft(
            "root", parent=None, name=name, kind=SpanKind.INTERNAL, start=start, end=end, order=0, attributes=attributes
        )
        error_type = run_error_type(timeline)
        if error_type is not None and timeline.outcome is not None:
            root.fail(error_type, timeline.outcome.reason or "run failed")
        if fork is not None:
            # The fork continues the parent run's trace, so its root links to the parent's root span.
            root.links.append(
                SpanLink(
                    trace_id=trace_id_for(fork.parent_run_id),
                    span_id=span_id_for(fork.parent_run_id, "root"),
                    attributes={
                        f"{NAMESPACE}.link.type": "forked_from",
                        f"{NAMESPACE}.fork.step": fork.fork_step,
                    },
                )
            )
        return root

    def _bot_span(self, bot: str, *, start: int, order: int, allowed: tuple[str, ...]) -> _SpanDraft:
        """Create an ``invoke_agent {bot}`` span for one stretch of a bot's activity."""

        attributes: dict[str, Any] = {
            "gen_ai.operation.name": "invoke_agent",
            "gen_ai.agent.name": bot,
            "gen_ai.conversation.id": self.run_id,
        }
        if allowed:
            attributes[f"{NAMESPACE}.bot.allowed_tools"] = list(allowed)
        root = self.drafts[0]
        return self._draft(
            f"bot:{order}",
            parent=root.span_id,
            name=f"invoke_agent {bot}",
            kind=SpanKind.INTERNAL,
            start=start,
            end=root.end,
            order=order,
            attributes=attributes,
        )

    def _model_span(self, call: ModelCall, parent: _SpanDraft) -> None:
        """Create a ``chat``/``generate_content`` span for one provider call."""

        provider_name, operation, kind = provider_attributes(call.provider)
        model = _model_of(call)
        attributes: dict[str, Any] = {
            "gen_ai.operation.name": operation,
            "gen_ai.provider.name": provider_name,
        }
        if model:
            attributes["gen_ai.request.model"] = model
        attributes["gen_ai.conversation.id"] = self.run_id
        finish_reason = call.metadata.get("finish_reason")
        if isinstance(finish_reason, str) and finish_reason:
            attributes["gen_ai.response.finish_reasons"] = [finish_reason]
        input_tokens, output_tokens = _usage(call.metadata)
        if input_tokens is not None:
            attributes["gen_ai.usage.input_tokens"] = input_tokens
        if output_tokens is not None:
            attributes["gen_ai.usage.output_tokens"] = output_tokens
        attributes.update(_decision_attributes(call.decision))
        if call.output is not None:
            attributes[f"{NAMESPACE}.llm.directive"] = model_directive(call.output)[0]
        elif call.failure is None and not call.interrupted:
            attributes[f"{NAMESPACE}.action.incomplete"] = True
        if call.requested_seq <= self.timeline.inherited_through_seq:
            attributes[f"{NAMESPACE}.fork.inherited"] = True
        if self.include_content:
            attributes["gen_ai.input.messages"] = [_input_message(item) for item in call.inputs]
            if call.output is not None:
                attributes["gen_ai.output.messages"] = [_text_message("assistant", call.output)]
        start, end = nanos_between(call.started_at, call.ended_at)
        span = self._draft(
            f"seq:{call.requested_seq}",
            parent=parent.span_id,
            name=f"{operation} {model}" if model else operation,
            kind=kind,
            start=start,
            end=end,
            order=call.requested_seq,
            attributes=attributes,
        )
        if call.interrupted:
            span.fail("interrupted", call.failure or "interrupted before a result was recorded")
        elif call.output is None and call.failure is not None:
            span.fail(classify_failure(call.failure), call.failure)

    def _tool_span(self, call: ToolCall, parent: _SpanDraft) -> None:
        """Create an ``execute_tool`` span for one built-in or MCP tool call."""

        mcp = mcp_identity(call)
        attributes: dict[str, Any] = {
            "gen_ai.operation.name": "execute_tool",
            "gen_ai.tool.name": call.tool,
            "gen_ai.tool.type": "function",
        }
        call_id = call.decision.observations_used[0] if call.decision.observations_used else None
        if call_id:
            attributes["gen_ai.tool.call.id"] = call_id
        agent = call.agent or self.agent_name
        if agent is not None:
            attributes["gen_ai.agent.name"] = agent
        attributes["gen_ai.conversation.id"] = self.run_id
        if mcp is not None:
            attributes["mcp.method.name"] = "tools/call"
            protocol_version = call.metadata.get("mcp_protocol_version")
            if isinstance(protocol_version, str) and protocol_version:
                attributes["mcp.protocol.version"] = protocol_version
            attributes["network.transport"] = "pipe"
        attributes.update(_decision_attributes(call.decision))
        if mcp is not None:
            attributes[f"{NAMESPACE}.mcp.server"] = mcp[0]
            attributes[f"{NAMESPACE}.mcp.tool"] = mcp[1]
            era = call.metadata.get("mcp_era")
            if isinstance(era, str) and era:
                attributes[f"{NAMESPACE}.mcp.era"] = era
        if call.ok is not None:
            attributes[f"{NAMESPACE}.tool.ok"] = call.ok
        elif call.failure is None and not call.interrupted:
            attributes[f"{NAMESPACE}.action.incomplete"] = True
        if call.requested_seq <= self.timeline.inherited_through_seq:
            attributes[f"{NAMESPACE}.fork.inherited"] = True
        if self.include_content:
            attributes["gen_ai.tool.call.arguments"] = redact_value(tool_arguments(call))
            if call.ok and call.content is not None:
                attributes["gen_ai.tool.call.result"] = redact_value(to_json_object(call.content, "content"))
        start, end = nanos_between(call.started_at, call.ended_at)
        span = self._draft(
            f"seq:{call.requested_seq}",
            parent=parent.span_id,
            name=f"execute_tool {call.tool}",
            kind=SpanKind.INTERNAL,
            start=start,
            end=end,
            order=call.requested_seq,
            attributes=attributes,
        )
        error_type = tool_error_type(call)
        if error_type is not None:
            span.fail(error_type, call.content or call.failure or error_type)

    def _handoff(self, handoff: Handoff, agent_span: _SpanDraft, root: _SpanDraft) -> _SpanDraft:
        """Record a handoff event and open the target bot's span."""

        attributes: dict[str, Any] = {}
        if handoff.from_bot is not None:
            attributes[f"{NAMESPACE}.handoff.from_bot"] = handoff.from_bot
        attributes[f"{NAMESPACE}.handoff.to_bot"] = handoff.to_bot
        attributes.update(_decision_attributes(handoff.decision, brief=True))
        if not handoff.completed:
            attributes[f"{NAMESPACE}.handoff.completed"] = False
        if self.include_content:
            attributes[f"{NAMESPACE}.handoff.summary"] = redact_text(handoff.summary)
        at = timestamp_to_unix_nanos(handoff.at)
        agent_span.events.append(SpanEvent(f"{NAMESPACE}.handoff", at, attributes))
        if not handoff.completed:
            return agent_span
        if agent_span is not root:
            agent_span.end = at
        return self._bot_span(handoff.to_bot, start=at, order=handoff.seq, allowed=handoff.allowed_tools)

    def _approval_event(self, approval: Approval) -> SpanEvent:
        """Return the span event for a human approval."""

        attributes: dict[str, Any] = {
            f"{NAMESPACE}.approval.tool": approval.tool,
            f"{NAMESPACE}.approval.status": approval.status,
        }
        if approval.request_id is not None:
            attributes[f"{NAMESPACE}.approval.request_id"] = approval.request_id
        return SpanEvent(f"{NAMESPACE}.approval", timestamp_to_unix_nanos(approval.at), attributes)

    def _decision_event(self, decision: DecisionRef) -> SpanEvent:
        """Return the root span event for a ``finish``/``fail``/``cancel`` decision."""

        attributes: dict[str, Any] = {f"{NAMESPACE}.decision.action": decision.action}
        attributes.update(_decision_attributes(decision))
        return SpanEvent(f"{NAMESPACE}.decision", timestamp_to_unix_nanos(decision.timestamp), attributes)

    def _fork_event(self, fork: Fork) -> SpanEvent:
        """Return the root span event for a fork point (the run's own, or an ancestor's among its copies)."""

        attributes: dict[str, Any] = {
            f"{NAMESPACE}.fork.parent_run_id": fork.parent_run_id,
            f"{NAMESPACE}.fork.step": fork.fork_step,
            f"{NAMESPACE}.fork.inherited_events": fork.inherited_events,
        }
        if not fork.own:
            attributes[f"{NAMESPACE}.fork.ancestor"] = True
        return SpanEvent(f"{NAMESPACE}.run.forked", timestamp_to_unix_nanos(fork.at), attributes)

    def _checkpoint_event(self, checkpoint: Checkpoint) -> SpanEvent:
        """Return the root span event for a checkpoint."""

        attributes: dict[str, Any] = {}
        if checkpoint.step is not None:
            attributes[f"{NAMESPACE}.checkpoint.step"] = checkpoint.step
        if checkpoint.active_bot_id is not None:
            attributes[f"{NAMESPACE}.checkpoint.active_bot"] = checkpoint.active_bot_id
        return SpanEvent(f"{NAMESPACE}.checkpoint", timestamp_to_unix_nanos(checkpoint.at), attributes)

    def _draft(
        self,
        key: str,
        *,
        parent: str | None,
        name: str,
        kind: SpanKind,
        start: int,
        end: int,
        order: int,
        attributes: dict[str, Any],
    ) -> _SpanDraft:
        """Create and register a span draft with a deterministic id."""

        draft = _SpanDraft(
            span_id=span_id_for(self.run_id, key),
            parent_span_id=parent,
            name=name,
            kind=kind,
            start=start,
            end=end,
            order=order,
            attributes=attributes,
        )
        self.drafts.append(draft)
        return draft

    def _model_calls(self) -> list[ModelCall]:
        """Return the run's provider calls."""

        return [step for step in self.timeline.steps if isinstance(step, ModelCall)]


def _decision_attributes(decision: DecisionRef, *, brief: bool = False) -> dict[str, Any]:
    """Return the rationale-trace attributes of a decision."""

    attributes: dict[str, Any] = {f"{NAMESPACE}.decision.seq": decision.seq}
    if decision.rule_id:
        attributes[f"{NAMESPACE}.decision.rule_id"] = decision.rule_id
    if not brief:
        if decision.explanation:
            attributes[f"{NAMESPACE}.decision.explanation"] = redact_text(decision.explanation)
        if decision.rejected_actions:
            attributes[f"{NAMESPACE}.decision.rejected_actions"] = list(decision.rejected_actions)
    return attributes


def _model_of(call: ModelCall) -> str | None:
    """Return the model recorded by the adapter, if any."""

    model = call.metadata.get("model")
    return model if isinstance(model, str) and model else None


def _usage(metadata: Mapping[str, Any]) -> tuple[int | None, int | None]:
    """Return ``(input_tokens, output_tokens)`` when the adapter recorded token usage."""

    sources = [metadata, metadata.get("usage"), metadata.get("usageMetadata")]
    input_tokens = _first_count(sources, ("input_tokens", "prompt_tokens", "promptTokenCount"))
    output_tokens = _first_count(sources, ("output_tokens", "completion_tokens", "candidatesTokenCount"))
    return input_tokens, output_tokens


def _first_count(sources: Sequence[Any], keys: Sequence[str]) -> int | None:
    """Return the first non-negative integer found under ``keys`` in the mapping ``sources``."""

    for source in sources:
        if not isinstance(source, Mapping):
            continue
        for key in keys:
            value = source.get(key)
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                return value
    return None


def _text_message(role: str, text: str) -> dict[str, Any]:
    """Return a GenAI chat message with one redacted text part."""

    return {"role": role, "parts": [{"type": "text", "content": redact_text(text)}]}


def _input_message(observation: ObservationRef) -> dict[str, Any]:
    """Map an observation onto a GenAI input message (role by observation source)."""

    source = observation.source
    if source.startswith("llm:"):
        return _text_message("assistant", observation.content)
    if source.startswith("tool:"):
        return {
            "role": "tool",
            "parts": [{"type": "tool_call_response", "response": redact_text(observation.content)}],
            "name": source.removeprefix("tool:"),
        }
    if source.startswith("handoff:"):
        return _text_message("system", observation.content)
    return _text_message("user", observation.content)


def tool_arguments(call: ToolCall) -> dict[str, Any]:
    """Return a tool call's arguments as an object (unredacted; callers must redact).

    Structured MCP arguments are used when recorded; a ``{"text": ...}`` payload holding a
    serialized JSON object is deserialized on a best-effort basis.

    Args:
        call: Tool call.

    Returns:
        Arguments object.
    """

    mcp_arguments = call.metadata.get("mcp_arguments")
    if isinstance(mcp_arguments, Mapping):
        return dict(mcp_arguments)
    payload = dict(call.decision.payload)
    text = payload.get("text")
    if set(payload) == {"text"} and isinstance(text, str):
        return to_json_object(text, "text")
    return payload


def _hex_id(*parts: str, digits: int) -> str:
    """Return ``digits`` hex digits of a namespaced SHA-256 digest, never all zeros."""

    digest = hashlib.sha256("\x1f".join(("multi-bot-agentic", *parts)).encode("utf-8")).hexdigest()[:digits]
    # All-zero ids are invalid in W3C Trace Context and OTLP; a SHA-256 prefix is practically
    # never zero, but the fallback keeps the id valid if it ever is.
    return digest if digest.strip("0") else digest[:-1] + "1"
