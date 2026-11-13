"""Tests for the OpenTelemetry GenAI span builder and the OTLP/JSON encoder."""

from __future__ import annotations

import base64
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import pytest

from multi_bot_agentic.approval import ApprovalDecision, HitlApprovalGate, record_approval
from multi_bot_agentic.bots import BotSpec
from multi_bot_agentic.event_log import EventRecord, SQLiteEventLog
from multi_bot_agentic.llm.fake import FakeLLMAdapter
from multi_bot_agentic.models import EventType, ModelOutput, ModelRequest, RunState
from multi_bot_agentic.runner import AgentRunner, build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tracing import (
    SpanKind,
    StatusCode,
    Trace,
    TraceInputError,
    build_trace,
    encode_any_value,
    render_otlp_json,
    select_latest_run,
    trace_to_otlp,
)
from multi_bot_agentic.tracing.privacy import redact_text, redact_value
from multi_bot_agentic.tracing.spans import Span, classify_failure, provider_attributes, span_id_for, trace_id_for
from multi_bot_agentic.tracing.timeline import timestamp_to_unix_nanos

GOAL = "Create a launch checklist for an AI agent platform"
# Obvious fake credentials; the redactors must keep every one of them out of exported traces.
FAKE_KEY = "sk-FAKEtrace0123456789abcdefXYZ"
FAKE_EMAIL = "ops-oncall@example.com"
HEX32 = re.compile(r"^[0-9a-f]{32}$")
HEX16 = re.compile(r"^[0-9a-f]{16}$")


class _CrashError(BaseException):
    """Stands in for the process dying mid-call: the runner cannot record a terminal event."""


class _ScriptedProvider:
    """Provider that replays scripted outputs (or raises scripted errors) with OpenAI-like metadata."""

    def __init__(self, *script: str | BaseException, provider_name: str = "openai", model: str = "gpt-6.1-sol") -> None:
        self.provider_name = provider_name
        self.model = model
        self.script = list(script)
        self.calls = 0

    def complete(self, request: ModelRequest, timeout_seconds: float) -> ModelOutput:
        del request, timeout_seconds
        self.calls += 1
        item = self.script.pop(0)
        if isinstance(item, BaseException):
            raise item
        raw = {
            "model": self.model,
            "finish_reason": "stop",
            "usage": {"prompt_tokens": 100 + self.calls, "completion_tokens": 10 * self.calls},
        }
        return ModelOutput(provider=self.provider_name, text=item, raw=raw)


def _bots() -> dict[str, BotSpec]:
    return {
        "planner": BotSpec(bot_id="planner", name="Planner", allowed_tools=frozenset({"checklist"})),
        "writer": BotSpec(bot_id="writer", name="Writer", allowed_tools=frozenset({"echo"})),
    }


def _fake_run(tmp_path: Path, goal: str = GOAL, run_id: str = "trace-run") -> list[EventRecord]:
    """Run the real runner with the deterministic fake provider and return the run's events."""

    log = SQLiteEventLog(tmp_path / "runs.sqlite")
    try:
        runner = AgentRunner(
            provider=FakeLLMAdapter(),
            event_log=log,
            tools=build_default_tools(root=tmp_path),
            safety_policy=SafetyPolicy(max_steps=5),
        )
        assert runner.run(goal, run_id=run_id).state == RunState.SUCCEEDED
        return log.list_events(run_id)
    finally:
        log.close()


def _scripted_run(
    tmp_path: Path,
    provider: _ScriptedProvider,
    *,
    run_id: str,
    bots: bool = False,
    goal: str = "Ship release v2",
) -> list[EventRecord]:
    """Run the real runner with a scripted provider and return the run's events."""

    log = SQLiteEventLog(tmp_path / "runs.sqlite")
    try:
        runner = AgentRunner(
            provider=provider,
            event_log=log,
            tools=build_default_tools(root=tmp_path),
            safety_policy=SafetyPolicy(max_steps=8, allowed_tools=frozenset({"checklist", "echo"})),
            bots=_bots() if bots else None,
            active_bot_id="planner" if bots else None,
        )
        runner.run(goal, run_id=run_id)
        return log.list_events(run_id)
    finally:
        log.close()


def _by_name(trace: Trace) -> dict[str, list[Span]]:
    spans: dict[str, list[Span]] = {}
    for span in trace.spans:
        spans.setdefault(span.name, []).append(span)
    return spans


def _event_time(events: list[EventRecord], seq: int) -> int:
    return timestamp_to_unix_nanos(next(event.timestamp for event in events if event.seq == seq))


def test_fake_run_builds_root_chat_and_tool_spans(tmp_path: Path) -> None:
    """A real fake-provider run becomes invoke_agent -> chat, execute_tool, chat."""

    events = _fake_run(tmp_path)
    trace = build_trace(events)

    assert [span.name for span in trace.spans] == ["invoke_agent", "chat", "execute_tool checklist", "chat"]
    root, first_chat, tool, second_chat = trace.spans
    assert root.parent_span_id is None
    assert {span.parent_span_id for span in trace.spans[1:]} == {root.span_id}
    assert [span.kind for span in trace.spans] == [SpanKind.INTERNAL] * 4
    assert HEX32.match(trace.trace_id)
    assert all(HEX16.match(span.span_id) for span in trace.spans)
    assert len({span.span_id for span in trace.spans}) == 4
    assert all(span.status_code is StatusCode.UNSET for span in trace.spans)
    assert root.start_time_unix_nano == _event_time(events, 1)
    assert root.end_time_unix_nano == _event_time(events, events[-1].seq)
    for child in trace.spans[1:]:
        assert root.start_time_unix_nano <= child.start_time_unix_nano <= child.end_time_unix_nano
        assert child.end_time_unix_nano <= root.end_time_unix_nano
    assert first_chat.end_time_unix_nano <= tool.start_time_unix_nano <= second_chat.start_time_unix_nano


def test_span_times_come_from_action_requested_and_action_result_events(tmp_path: Path) -> None:
    """Action spans start at action_requested and end at the matching action_result."""

    events = _fake_run(tmp_path)
    trace = build_trace(events)
    requested = [event for event in events if event.event_type == "action_requested"]
    results = [event for event in events if event.event_type == "action_result"]

    for span, start_event, end_event in zip(trace.spans[1:], requested, results, strict=True):
        assert span.start_time_unix_nano == timestamp_to_unix_nanos(start_event.timestamp)
        assert span.end_time_unix_nano == timestamp_to_unix_nanos(end_event.timestamp)


def test_semantic_convention_attributes_on_fake_run(tmp_path: Path) -> None:
    """Root, chat, and execute_tool spans carry the GenAI semantic-convention attributes."""

    events = _fake_run(tmp_path)
    root, chat, tool, _ = build_trace(events).spans

    assert root.attributes["gen_ai.operation.name"] == "invoke_agent"
    assert root.attributes["gen_ai.conversation.id"] == "trace-run"
    assert "gen_ai.agent.name" not in root.attributes
    assert root.attributes["multi_bot_agentic.run.state"] == "succeeded"
    assert root.attributes["multi_bot_agentic.run.steps"] == 4
    assert root.attributes["multi_bot_agentic.run.provider"] == "fake"
    assert root.attributes["multi_bot_agentic.run.event_count"] == len(events)
    assert [event.name for event in root.events] == ["multi_bot_agentic.checkpoint"] * 3 + [
        "multi_bot_agentic.decision"
    ]
    finish = root.events[-1].attributes
    assert finish["multi_bot_agentic.decision.action"] == "finish"
    assert finish["multi_bot_agentic.decision.rule_id"] == "model.done-or-budget"

    assert chat.attributes["gen_ai.operation.name"] == "chat"
    assert chat.attributes["gen_ai.provider.name"] == "fake"
    assert chat.attributes["gen_ai.conversation.id"] == "trace-run"
    assert chat.attributes["multi_bot_agentic.decision.rule_id"] == "observe.no-model-output"
    assert chat.attributes["multi_bot_agentic.decision.rejected_actions"] == ["call_tool", "finish"]
    assert chat.attributes["multi_bot_agentic.llm.directive"] == "tool"

    decision = next(
        event for event in events if event.event_type == "decision" and event.payload["action"] == "call_tool"
    )
    assert tool.attributes["gen_ai.operation.name"] == "execute_tool"
    assert tool.attributes["gen_ai.tool.name"] == "checklist"
    assert tool.attributes["gen_ai.tool.type"] == "function"
    assert tool.attributes["gen_ai.tool.call.id"] == decision.payload["rationale"]["observations_used"][0]
    assert tool.attributes["multi_bot_agentic.decision.seq"] == decision.seq
    assert tool.attributes["multi_bot_agentic.decision.rule_id"] == "model.requested-tool"
    assert tool.attributes["multi_bot_agentic.tool.ok"] is True
    assert "mcp.method.name" not in tool.attributes


def test_ids_are_derived_from_run_id_and_exports_are_byte_identical(tmp_path: Path) -> None:
    """The same run always exports the same ids and the same bytes."""

    events = _fake_run(tmp_path)
    first = render_otlp_json(build_trace(events))
    log = SQLiteEventLog(tmp_path / "runs.sqlite")
    try:
        reread = log.list_events("trace-run")
    finally:
        log.close()
    second = render_otlp_json(build_trace(list(reversed(reread))))

    assert first == second
    trace = build_trace(events)
    digest = hashlib.sha256("\x1f".join(("multi-bot-agentic", "trace", "trace-run")).encode()).hexdigest()
    assert trace.trace_id == digest[:32] == trace_id_for("trace-run")
    assert trace.root.span_id == span_id_for("trace-run", "root")
    assert trace.spans[1].span_id == span_id_for("trace-run", "seq:7")
    assert trace_id_for("another-run") != trace.trace_id


def test_content_is_opt_in_and_secrets_never_leave_the_process(tmp_path: Path) -> None:
    """Prompts, outputs, and tool payloads are exported only on request, and always redacted."""

    goal = f"Rotate {FAKE_KEY} and page {FAKE_EMAIL} before launch"
    events = _fake_run(tmp_path, goal=goal)
    default_json = render_otlp_json(build_trace(events))
    content_trace = build_trace(events, include_content=True)
    content_json = render_otlp_json(content_trace)

    for exported in (default_json, content_json):
        assert FAKE_KEY not in exported
        assert FAKE_EMAIL not in exported
    for attribute in ("gen_ai.input.messages", "gen_ai.output.messages", "gen_ai.tool.call.arguments"):
        assert attribute not in default_json
    assert "Rotate" not in default_json

    root, chat, tool, _ = content_trace.spans
    assert root.attributes["gen_ai.input.messages"] == [
        {"role": "user", "parts": [{"type": "text", "content": "Rotate [TOKEN] and page [EMAIL] before launch"}]}
    ]
    assert root.attributes["gen_ai.output.messages"][0]["role"] == "assistant"
    assert chat.attributes["gen_ai.input.messages"][0]["parts"][0]["content"].startswith("Rotate [TOKEN]")
    assert chat.attributes["gen_ai.output.messages"][0]["parts"][0]["content"].startswith(
        "TOOL:checklist:Rotate [TOKEN]"
    )
    assert tool.attributes["gen_ai.tool.call.arguments"] == {"text": "Rotate [TOKEN] and page [EMAIL] before launch"}
    assert "[TOKEN]" in tool.attributes["gen_ai.tool.call.result"]["content"]


def test_structured_tool_arguments_hide_sensitive_keys(tmp_path: Path) -> None:
    """JSON tool arguments are deserialized; sensitive keys are replaced even inside model text."""

    secret = "hunter2-not-a-real-secret"
    provider = _ScriptedProvider(f'TOOL:echo:{{"text": "hi", "api_key": "{secret}"}}', "DONE: echoed")
    events = _scripted_run(tmp_path, provider, run_id="args-run")
    trace = build_trace(events, include_content=True)
    tool = _by_name(trace)["execute_tool echo"][0]

    assert tool.attributes["gen_ai.tool.call.arguments"] == {"text": "hi", "api_key": "[REDACTED]"}
    assert secret not in render_otlp_json(trace)


def test_handoff_run_nests_spans_under_bot_spans(tmp_path: Path) -> None:
    """Each bot's stretch of the run becomes an invoke_agent span; the handoff is a span event."""

    provider = _ScriptedProvider("TOOL:checklist:ship v2", "HANDOFF:writer:draft the note", "DONE: drafted")
    events = _scripted_run(tmp_path, provider, run_id="handoff-run", bots=True)
    trace = build_trace(events)
    spans = _by_name(trace)
    root = trace.root
    planner, writer = spans["invoke_agent planner"][0], spans["invoke_agent writer"][0]
    handoff_event = next(event for event in events if event.payload.get("kind") == "handoff")

    assert [span.name for span in trace.spans] == [
        "invoke_agent",
        "invoke_agent planner",
        "chat gpt-6.1-sol",
        "execute_tool checklist",
        "chat gpt-6.1-sol",
        "invoke_agent writer",
        "chat gpt-6.1-sol",
    ]
    assert planner.parent_span_id == writer.parent_span_id == root.span_id
    assert {span.parent_span_id for span in trace.spans[2:5]} == {planner.span_id}
    assert trace.spans[6].parent_span_id == writer.span_id
    assert planner.attributes["gen_ai.agent.name"] == "planner"
    assert writer.attributes["gen_ai.operation.name"] == "invoke_agent"
    assert writer.attributes["multi_bot_agentic.bot.allowed_tools"] == ["echo"]
    assert planner.end_time_unix_nano == writer.start_time_unix_nano == _event_time(events, handoff_event.seq)
    assert writer.end_time_unix_nano == root.end_time_unix_nano
    assert spans["execute_tool checklist"][0].attributes["gen_ai.agent.name"] == "planner"

    (handoff,) = planner.events
    assert handoff.name == "multi_bot_agentic.handoff"
    assert handoff.attributes["multi_bot_agentic.handoff.from_bot"] == "planner"
    assert handoff.attributes["multi_bot_agentic.handoff.to_bot"] == "writer"
    assert handoff.attributes["multi_bot_agentic.decision.rule_id"] == "model.requested-handoff"
    assert "multi_bot_agentic.handoff.summary" not in handoff.attributes
    with_content = build_trace(events, include_content=True)
    summary = (
        _by_name(with_content)["invoke_agent planner"][0].events[0].attributes["multi_bot_agentic.handoff.summary"]
    )
    assert summary == "draft the note"


def test_chat_spans_carry_provider_model_and_token_usage(tmp_path: Path) -> None:
    """Recorded model, finish reason, and token usage map to gen_ai.* attributes."""

    provider = _ScriptedProvider("TOOL:checklist:ship v2", "DONE: shipped")
    trace = build_trace(_scripted_run(tmp_path, provider, run_id="usage-run"))
    first, second = _by_name(trace)["chat gpt-6.1-sol"]

    assert first.kind is SpanKind.CLIENT
    assert first.attributes["gen_ai.provider.name"] == "openai"
    assert first.attributes["gen_ai.request.model"] == "gpt-6.1-sol"
    assert first.attributes["gen_ai.response.finish_reasons"] == ["stop"]
    assert (first.attributes["gen_ai.usage.input_tokens"], first.attributes["gen_ai.usage.output_tokens"]) == (101, 10)
    assert (second.attributes["gen_ai.usage.input_tokens"], second.attributes["gen_ai.usage.output_tokens"]) == (
        102,
        20,
    )
    assert trace.root.attributes["gen_ai.request.model"] == "gpt-6.1-sol"
    assert trace.root.attributes["gen_ai.usage.input_tokens"] == 203
    assert trace.root.attributes["gen_ai.usage.output_tokens"] == 30


@pytest.mark.parametrize(
    ("provider", "expected"),
    [
        ("openai", ("openai", "chat", SpanKind.CLIENT)),
        ("kimi", ("moonshot_ai", "chat", SpanKind.CLIENT)),
        ("gemini", ("gcp.gemini", "generate_content", SpanKind.CLIENT)),
        ("claude_code", ("anthropic", "chat", SpanKind.CLIENT)),
        ("fake", ("fake", "chat", SpanKind.INTERNAL)),
    ],
)
def test_provider_names_map_to_well_known_values(provider: str, expected: tuple[str, str, SpanKind]) -> None:
    """Adapters map to well-known gen_ai.provider.name and gen_ai.operation.name values."""

    assert provider_attributes(provider) == expected


def test_provider_failure_marks_chat_and_root_spans_as_errors(tmp_path: Path) -> None:
    """A provider error without a result ends the chat span at the next event with status ERROR."""

    provider = _ScriptedProvider(RuntimeError(f"HTTP Error 503: Service Unavailable (key {FAKE_KEY})"))
    events = _scripted_run(tmp_path, provider, run_id="outage-run")
    trace = build_trace(events)
    root, chat = trace.spans
    requested = next(event for event in events if event.event_type == "action_requested")

    assert chat.status_code is StatusCode.ERROR
    assert chat.attributes["error.type"] == "503"
    assert chat.start_time_unix_nano == _event_time(events, requested.seq)
    assert chat.end_time_unix_nano == _event_time(events, requested.seq + 1)
    assert "multi_bot_agentic.llm.directive" not in chat.attributes
    assert root.status_code is StatusCode.ERROR
    assert root.attributes["error.type"] == "503"
    assert root.attributes["multi_bot_agentic.run.state"] == "failed"
    assert root.status_message.startswith("HTTP Error 503: Service Unavailable")
    assert FAKE_KEY not in root.status_message
    assert "[TOKEN]" in chat.status_message


def test_fail_decision_reports_its_rule_as_error_type(tmp_path: Path) -> None:
    """A run failed by a fail decision reports the rule id as error.type."""

    provider = _ScriptedProvider("HANDOFF:ghost:take over")
    trace = build_trace(_scripted_run(tmp_path, provider, run_id="ghost-run", bots=True))

    assert trace.root.status_code is StatusCode.ERROR
    assert trace.root.attributes["error.type"] == "model.unknown-handoff-bot"
    assert trace.root.status_message == "unknown bot for handoff: ghost"
    decision = trace.root.events[-1]
    assert decision.attributes["multi_bot_agentic.decision.action"] == "fail"


def test_failed_builtin_tool_sets_tool_error(tmp_path: Path) -> None:
    """A tool result with ok=false is an ERROR execute_tool span with error.type tool_error."""

    log = SQLiteEventLog(tmp_path / "runs.sqlite")
    try:
        log.append("tool-fail", RunState.CREATED, EventType.RUN_CREATED, {"goal": "g", "provider": "openai"})
        _append_tool_attempt(log, "tool-fail", ok=False, content="echo requires non-empty text")
        events = log.list_events("tool-fail")
    finally:
        log.close()
    tool = _by_name(build_trace(events))["execute_tool echo"][0]

    assert tool.status_code is StatusCode.ERROR
    assert tool.attributes["error.type"] == "tool_error"
    assert tool.attributes["multi_bot_agentic.tool.ok"] is False
    assert tool.status_message == "echo requires non-empty text"


def test_mcp_tool_spans_carry_mcp_attributes(tmp_path: Path) -> None:
    """MCP calls get mcp.* attributes on the execute_tool span instead of a separate span."""

    log = SQLiteEventLog(tmp_path / "runs.sqlite")
    metadata = {
        "mcp_server": "notes",
        "mcp_tool": "search_notes",
        "mcp_arguments": {"query": "release", "token": "abc123"},
        "mcp_era": "modern",
        "mcp_protocol_version": "2026-07-28",
        "duration_ms": 3,
        "error_kind": "tool_error",
    }
    try:
        log.append("mcp-run", RunState.CREATED, EventType.RUN_CREATED, {"goal": "g", "provider": "fake"})
        _append_tool_attempt(
            log, "mcp-run", tool="mcp__notes__search_notes", ok=False, content="no such note", metadata=metadata
        )
        events = log.list_events("mcp-run")
    finally:
        log.close()
    trace = build_trace(events, include_content=True)
    tool = trace.spans[1]

    assert tool.name == "execute_tool mcp__notes__search_notes"
    assert tool.attributes["mcp.method.name"] == "tools/call"
    assert tool.attributes["mcp.protocol.version"] == "2026-07-28"
    assert tool.attributes["network.transport"] == "pipe"
    assert tool.attributes["multi_bot_agentic.mcp.server"] == "notes"
    assert tool.attributes["multi_bot_agentic.mcp.tool"] == "search_notes"
    assert tool.attributes["multi_bot_agentic.mcp.era"] == "modern"
    assert tool.attributes["error.type"] == "tool_error"
    assert tool.attributes["gen_ai.tool.call.arguments"] == {"query": "release", "token": "[REDACTED]"}
    assert "gen_ai.tool.call.result" not in tool.attributes


def test_approval_events_attach_to_the_active_agent_span(tmp_path: Path) -> None:
    """Approvals recorded with record_approval become span events."""

    log = SQLiteEventLog(tmp_path / "runs.sqlite")
    gate = HitlApprovalGate(approval_dir=tmp_path / "approvals", tools_requiring_approval=frozenset({"deploy"}))
    try:
        runner = AgentRunner(
            provider=FakeLLMAdapter(),
            event_log=log,
            tools=build_default_tools(root=tmp_path),
            safety_policy=SafetyPolicy(max_steps=5),
        )
        runner.run(GOAL, run_id="approval-run")
        request = gate.request(run_id="approval-run", tool_name="deploy", payload=f"prod {FAKE_KEY}")
        record_approval(log, request)
        record_approval(log, gate.resolve(request.request_id, ApprovalDecision.REJECTED))
        events = log.list_events("approval-run")
    finally:
        log.close()
    trace = build_trace(events)
    approvals = [event for event in trace.root.events if event.name == "multi_bot_agentic.approval"]

    assert [event.attributes["multi_bot_agentic.approval.status"] for event in approvals] == ["pending", "rejected"]
    assert approvals[0].attributes["multi_bot_agentic.approval.tool"] == "deploy"
    assert approvals[0].attributes["multi_bot_agentic.approval.request_id"] == request.request_id
    assert FAKE_KEY not in render_otlp_json(build_trace(events, include_content=True))


def test_resumed_run_marks_the_interrupted_call_and_records_the_resume(tmp_path: Path) -> None:
    """A crash mid-call leaves an interrupted span; the resume is a root span event."""

    log = SQLiteEventLog(tmp_path / "runs.sqlite")
    try:
        crashing = AgentRunner(
            provider=_ScriptedProvider("TOOL:checklist:ship", _CrashError()),
            event_log=log,
            tools=build_default_tools(root=tmp_path),
            safety_policy=SafetyPolicy(max_steps=8, allowed_tools=frozenset({"checklist"})),
        )
        with pytest.raises(_CrashError):
            crashing.run("Ship release v2", run_id="resume-run")
        resumed = AgentRunner(
            provider=_ScriptedProvider("DONE: shipped after resume"),
            event_log=log,
            tools=build_default_tools(root=tmp_path),
            safety_policy=SafetyPolicy(max_steps=8, allowed_tools=frozenset({"checklist"})),
        )
        assert resumed.resume("resume-run").state == RunState.SUCCEEDED
        events = log.list_events("resume-run")
    finally:
        log.close()
    trace = build_trace(events)
    chats = [span for span in trace.spans if span.attributes["gen_ai.operation.name"] == "chat"]

    assert [chat.status_code for chat in chats] == [StatusCode.UNSET, StatusCode.ERROR, StatusCode.UNSET]
    interrupted = chats[1]
    # No result was recorded, so the model is unknown and the span is named after the operation only.
    assert interrupted.name == "chat"
    assert interrupted.attributes["error.type"] == "interrupted"
    assert interrupted.start_time_unix_nano == interrupted.end_time_unix_nano
    assert trace.root.attributes["multi_bot_agentic.run.resume_count"] == 1
    assert trace.root.attributes["multi_bot_agentic.run.state"] == "succeeded"
    assert "multi_bot_agentic.run.resumed" in [event.name for event in trace.root.events]


def test_unfinished_run_exports_an_incomplete_action(tmp_path: Path) -> None:
    """A run without a terminal event (still running) is exported as unfinished."""

    events = _fake_run(tmp_path)
    cut = next(event.seq for event in events if event.event_type == "action_requested")
    trace = build_trace([event for event in events if event.seq <= cut])
    root, chat = trace.spans

    assert root.attributes["multi_bot_agentic.run.state"] == "unfinished"
    assert root.status_code is StatusCode.UNSET
    assert chat.attributes["multi_bot_agentic.action.incomplete"] is True
    assert chat.status_code is StatusCode.UNSET
    assert chat.start_time_unix_nano == chat.end_time_unix_nano


def test_agent_name_names_the_root_span(tmp_path: Path) -> None:
    """--agent-name sets gen_ai.agent.name and the root span name."""

    trace = build_trace(_fake_run(tmp_path), agent_name="release-bot")

    assert trace.root.name == "invoke_agent release-bot"
    assert trace.root.attributes["gen_ai.agent.name"] == "release-bot"
    assert trace.spans[2].attributes["gen_ai.agent.name"] == "release-bot"


def test_otlp_json_is_a_valid_export_trace_service_request(tmp_path: Path) -> None:
    """Validate the OTLP/JSON ExportTraceServiceRequest structure field by field."""

    trace = build_trace(_fake_run(tmp_path), include_content=True)
    payload = json.loads(render_otlp_json(trace))

    assert list(payload) == ["resourceSpans"]
    (resource_spans,) = payload["resourceSpans"]
    assert set(resource_spans) == {"resource", "scopeSpans"}
    resource = _attributes(resource_spans["resource"]["attributes"])
    assert resource["service.name"] == {"stringValue": "multi-bot-agentic"}
    assert set(resource["service.version"]) == {"stringValue"}
    (scope_spans,) = resource_spans["scopeSpans"]
    assert scope_spans["scope"]["name"] == "multi_bot_agentic.tracing"
    assert scope_spans["scope"]["version"] == resource["service.version"]["stringValue"]
    spans = scope_spans["spans"]
    assert len(spans) == len(trace.spans)
    span_ids = {span["spanId"] for span in spans}
    for span in spans:
        assert set(span) <= {
            "traceId",
            "spanId",
            "parentSpanId",
            "name",
            "kind",
            "startTimeUnixNano",
            "endTimeUnixNano",
            "attributes",
            "events",
            "status",
        }
        assert span["traceId"] == trace.trace_id and HEX32.match(span["traceId"])
        assert HEX16.match(span["spanId"])
        if span is spans[0]:
            assert "parentSpanId" not in span
        else:
            assert span["parentSpanId"] in span_ids
        assert isinstance(span["kind"], int) and span["kind"] in {1, 3}
        assert re.fullmatch(r"\d{19}", span["startTimeUnixNano"])
        assert re.fullmatch(r"\d{19}", span["endTimeUnixNano"])
        assert int(span["endTimeUnixNano"]) >= int(span["startTimeUnixNano"])
        for attribute in span["attributes"]:
            assert set(attribute) == {"key", "value"}
            _assert_any_value(attribute["value"])
        for event in span.get("events", []):
            assert set(event) == {"timeUnixNano", "name", "attributes"}
            assert re.fullmatch(r"\d{19}", event["timeUnixNano"])
            for attribute in event["attributes"]:
                _assert_any_value(attribute["value"])
        assert span["status"]["code"] in {0, 2}
    root = _attributes(spans[0]["attributes"])
    assert root["gen_ai.operation.name"] == {"stringValue": "invoke_agent"}
    assert root["multi_bot_agentic.run.steps"] == {"intValue": "4"}
    messages = root["gen_ai.input.messages"]["arrayValue"]["values"][0]["kvlistValue"]["values"]
    assert messages[0] == {"key": "role", "value": {"stringValue": "user"}}


def test_otlp_json_parses_with_opentelemetry_proto(tmp_path: Path) -> None:
    """When opentelemetry-proto is installed, the JSON parses into ExportTraceServiceRequest."""

    trace_service_pb2 = pytest.importorskip("opentelemetry.proto.collector.trace.v1.trace_service_pb2")
    json_format = pytest.importorskip("google.protobuf.json_format")
    trace = build_trace(_fake_run(tmp_path), include_content=True)
    payload = json.loads(render_otlp_json(trace))
    # OTLP/JSON hex-encodes ids; the generic protobuf JSON parser expects base64 bytes.
    for span in payload["resourceSpans"][0]["scopeSpans"][0]["spans"]:
        for key in ("traceId", "spanId", "parentSpanId"):
            if key in span:
                span[key] = base64.b64encode(bytes.fromhex(span[key])).decode()
    request = json_format.ParseDict(payload, trace_service_pb2.ExportTraceServiceRequest())

    parsed = request.resource_spans[0].scope_spans[0].spans
    assert [span.name for span in parsed] == [span.name for span in trace.spans]
    assert parsed[0].trace_id == bytes.fromhex(trace.trace_id)
    assert parsed[1].parent_span_id == bytes.fromhex(trace.root.span_id)
    assert parsed[0].start_time_unix_nano == trace.root.start_time_unix_nano


def test_encode_any_value_handles_every_json_type() -> None:
    """Booleans, 64-bit integers, floats, nulls, arrays, and objects map onto OTLP AnyValue."""

    assert encode_any_value(True) == {"boolValue": True}
    assert encode_any_value(7) == {"intValue": "7"}
    assert encode_any_value(1.5) == {"doubleValue": 1.5}
    assert encode_any_value(float("nan")) == {"stringValue": "nan"}
    assert encode_any_value(None) == {}
    assert encode_any_value(["a", 1]) == {"arrayValue": {"values": [{"stringValue": "a"}, {"intValue": "1"}]}}
    assert encode_any_value({"k": False}) == {"kvlistValue": {"values": [{"key": "k", "value": {"boolValue": False}}]}}


def test_trace_to_otlp_accepts_a_service_version_override(tmp_path: Path) -> None:
    """service.version and the scope version can be pinned."""

    payload = trace_to_otlp(build_trace(_fake_run(tmp_path)), service_version="9.9.9")
    resource_spans = payload["resourceSpans"][0]

    assert _attributes(resource_spans["resource"]["attributes"])["service.version"] == {"stringValue": "9.9.9"}
    assert resource_spans["scopeSpans"][0]["scope"]["version"] == "9.9.9"


def test_build_trace_rejects_empty_mixed_and_malformed_input(tmp_path: Path) -> None:
    """Invalid input raises TraceInputError with a clear message."""

    events = _fake_run(tmp_path)
    with pytest.raises(TraceInputError, match="no events"):
        build_trace([])
    other = EventRecord("other", 1, events[0].timestamp, "run_created", "created", {})
    with pytest.raises(TraceInputError, match="one run"):
        build_trace([*events, other])
    broken = EventRecord("trace-run", 99, "yesterday", "checkpoint", "acting", {})
    with pytest.raises(TraceInputError, match="event 99 of run trace-run: invalid event timestamp"):
        build_trace([*events, broken])


def test_select_latest_run_compares_parsed_timestamps() -> None:
    """The most recently active run wins, whatever the timestamp formatting."""

    assert select_latest_run({}) is None
    latest = select_latest_run(
        {
            "a": "2026-11-07T18:00:00.000001+00:00",
            "b": "2026-11-07T18:00:01+00:00",
            "c": "2026-11-07T10:30:00-08:00",
        }
    )
    assert latest == "c"
    assert select_latest_run({"x": "2026-11-07T18:00:00Z", "y": "2026-11-07T18:00:00+00:00"}) == "y"


@pytest.mark.parametrize(
    ("reason", "expected"),
    [
        ("HTTP Error 429: Too Many Requests", "429"),
        ("Claude Code timed out after 30s: claude", "timeout"),
        ("step budget exhausted", "step_budget_exhausted"),
        ("tool is not registered: nope", "_OTHER"),
    ],
)
def test_classify_failure(reason: str, expected: str) -> None:
    """Free-text failure reasons map to low-cardinality error.type values."""

    assert classify_failure(reason) == expected


def test_redaction_reuses_the_repository_scrubbers() -> None:
    """Free text and structured values are scrubbed with the existing redactor and sanitizer."""

    assert redact_text(f"Bearer abc.def and {FAKE_KEY} for {FAKE_EMAIL}") == "[TOKEN] and [TOKEN] for [EMAIL]"
    assert redact_text('call {"password": "p4ss", "x": 1} with token=abc') == (
        'call {"password": "[REDACTED]", "x": 1} with token=[REDACTED]'
    )
    assert redact_text("x" * 5000).endswith("...[truncated]")
    assert redact_value({"Authorization": {"nested": "value"}, "items": ["555-123-4567", 3, None]}) == {
        "Authorization": "[REDACTED]",
        "items": ["[PHONE]", 3, None],
    }


def _append_tool_attempt(
    log: SQLiteEventLog,
    run_id: str,
    *,
    tool: str = "echo",
    ok: bool,
    content: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Append a call_tool decision, its request, and its result."""

    decision = {
        "action": "call_tool",
        "target": tool,
        "payload": {"text": "payload"},
        "rationale": {
            "rule_id": "model.requested-tool",
            "explanation": "The latest model output requested an allowlisted tool action.",
            "observations_used": ["obs-1"],
            "rejected_actions": ["finish", "call_llm"],
        },
    }
    log.append(run_id, RunState.DECIDING, EventType.DECISION, decision)
    log.append(run_id, RunState.ACTING, EventType.ACTION_REQUESTED, decision)
    log.append(
        run_id,
        RunState.ACTING,
        EventType.ACTION_RESULT,
        {"kind": "tool", "tool": tool, "ok": ok, "content": content, "metadata": metadata or {}},
    )


def _attributes(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {item["key"]: item["value"] for item in items}


def _assert_any_value(value: dict[str, Any]) -> None:
    """Assert ``value`` is a well-formed OTLP/JSON AnyValue."""

    assert len(value) <= 1
    if "stringValue" in value:
        assert isinstance(value["stringValue"], str)
    elif "boolValue" in value:
        assert isinstance(value["boolValue"], bool)
    elif "intValue" in value:
        assert isinstance(value["intValue"], str) and re.fullmatch(r"-?\d+", value["intValue"])
    elif "doubleValue" in value:
        assert isinstance(value["doubleValue"], float)
    elif "arrayValue" in value:
        assert set(value["arrayValue"]) == {"values"}
        for item in value["arrayValue"]["values"]:
            _assert_any_value(item)
    elif "kvlistValue" in value:
        assert set(value["kvlistValue"]) == {"values"}
        for item in value["kvlistValue"]["values"]:
            assert set(item) == {"key", "value"}
            _assert_any_value(item["value"])
    else:
        assert value == {}
