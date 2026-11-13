"""Tests for the Mermaid sequence-diagram renderer."""

from __future__ import annotations

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
from multi_bot_agentic.tracing import mermaid_text, render_mermaid

GOAL = "Create a launch checklist for an AI agent platform"
FAKE_KEY = "sk-FAKEmermaid0123456789abcdefXYZ"

FAKE_RUN_DIAGRAM = """\
sequenceDiagram
    autonumber
    participant O as Orchestrator
    participant A1 as LLM fake
    participant T1 as checklist
    Note over O: run mermaid-run (provider fake)
    O->>A1: call_llm (observe.no-model-output)
    A1-->>O: TOOL checklist
    O->>T1: call_tool (model.requested-tool)
    T1-->>O: ok
    O->>A1: call_llm (tool.result-needs-synthesis)
    A1-->>O: DONE
    Note over O: finish (model.done-or-budget)
    Note over O: succeeded after 4 steps"""


class _ScriptedProvider:
    """Provider that replays scripted outputs or raises scripted errors."""

    def __init__(self, *script: str | BaseException) -> None:
        self.provider_name = "openai"
        self.script = list(script)

    def complete(self, request: ModelRequest, timeout_seconds: float) -> ModelOutput:
        del request, timeout_seconds
        item = self.script.pop(0)
        if isinstance(item, BaseException):
            raise item
        return ModelOutput(provider=self.provider_name, text=item, raw={"model": "gpt-6.1-sol"})


def _run(tmp_path: Path, provider: Any, *, run_id: str, goal: str = GOAL, bots: bool = False) -> list[EventRecord]:
    log = SQLiteEventLog(tmp_path / "runs.sqlite")
    try:
        runner = AgentRunner(
            provider=provider,
            event_log=log,
            tools=build_default_tools(root=tmp_path),
            safety_policy=SafetyPolicy(max_steps=8, allowed_tools=frozenset({"checklist", "echo"})),
            bots=(
                {
                    "planner": BotSpec(bot_id="planner", name="Planner", allowed_tools=frozenset({"checklist"})),
                    "writer": BotSpec(bot_id="writer", name="Writer", allowed_tools=frozenset({"echo"})),
                }
                if bots
                else None
            ),
            active_bot_id="planner" if bots else None,
        )
        runner.run(goal, run_id=run_id)
        return log.list_events(run_id)
    finally:
        log.close()


def _strip_entities(line: str) -> str:
    return re.sub(r"#\d+;", "", line)


def test_fake_run_diagram_snapshot(tmp_path: Path) -> None:
    """A real fake-provider run renders the same diagram every time."""

    events = _run(tmp_path, FakeLLMAdapter(), run_id="mermaid-run")

    assert render_mermaid(events) == FAKE_RUN_DIAGRAM
    assert render_mermaid(list(reversed(events))) == FAKE_RUN_DIAGRAM


def test_content_snippets_are_opt_in_and_redacted(tmp_path: Path) -> None:
    """Snippets of model output, tool arguments, and results appear only with include_content."""

    goal = f"Rotate {FAKE_KEY} before launch"
    events = _run(tmp_path, FakeLLMAdapter(), run_id="content-run", goal=goal)
    default = render_mermaid(events)
    content = render_mermaid(events, include_content=True).splitlines()

    assert "Rotate" not in default
    assert "    A1-->>O: TOOL checklist: Rotate [TOKEN] before launch" in content
    assert "    O->>T1: call_tool (model.requested-tool): Rotate [TOKEN] before launch" in content
    assert any(line.startswith("    T1-->>O: ok: - Define scope for Rotate [TOKEN]") for line in content)
    assert "    A1-->>O: DONE: synthesized plan from 3 observations" in content
    assert FAKE_KEY not in "\n".join(content)


def test_directive_targets_the_run_never_used_are_content(tmp_path: Path) -> None:
    """A malformed TOOL:/HANDOFF: "target" is model output: hidden by default, redacted with content."""

    leak = f"look up jane.doe@example.com with {FAKE_KEY}"
    provider = _ScriptedProvider(f"TOOL: {leak}", f"HANDOFF: {leak}", "TOOL:checklist:ship", "DONE: shipped")
    events = _run(tmp_path, provider, run_id="directive-run", bots=True)

    default = render_mermaid(events).splitlines()
    content = render_mermaid(events, include_content=True).splitlines()

    assert [line for line in default if line.startswith("    A1-->>O:")] == [
        "    A1-->>O: TOOL",
        "    A1-->>O: HANDOFF",
        "    A1-->>O: TOOL checklist",
        "    A1-->>O: DONE",
    ]
    assert "    A1-->>O: TOOL look up [EMAIL] with [TOKEN]:" in content
    assert "    A1-->>O: HANDOFF look up [EMAIL] with [TOKEN]:" in content
    assert "    A1-->>O: TOOL checklist: ship" in content
    for rendered in (default, content):
        assert "jane.doe" not in "\n".join(rendered)
        assert FAKE_KEY not in "\n".join(rendered)


def test_mermaid_text_escapes_syntax_characters() -> None:
    """Semicolons, hashes, quotes, comment markers, HTML, and line breaks become entity codes or spaces."""

    assert mermaid_text('a;b #c "d"\nnext\r\n%% <b> & caf\u00e9\u2026') == (
        "a#59;b #35;c #34;d#34; next #37;#37; #60;b#62; #38; caf#233;#8230;"
    )
    assert mermaid_text("x" * 20, limit=10) == "xxxxxxx..."
    assert mermaid_text("  spaced \t out  ") == "spaced out"


def test_hostile_text_cannot_break_the_diagram() -> None:
    """Injected Mermaid syntax stays inside escaped single-line messages."""

    run_id = 'weird #1; "q" <b>&amp; %%x end'
    decision = {
        "action": "call_tool",
        "target": "odd;tool#",
        "payload": {"text": "a;b\n-->> end"},
        "rationale": {
            "rule_id": "model.requested-tool",
            "explanation": "",
            "observations_used": [],
            "rejected_actions": [],
        },
    }
    events = [
        EventRecord(
            run_id, 1, "2026-11-07T18:00:01+00:00", "run_created", "created", {"goal": "g", "provider": "fake"}
        ),
        EventRecord(run_id, 2, "2026-11-07T18:00:02+00:00", "decision", "deciding", decision),
        EventRecord(run_id, 3, "2026-11-07T18:00:03+00:00", "action_requested", "acting", decision),
        EventRecord(
            run_id,
            4,
            "2026-11-07T18:00:04+00:00",
            "action_result",
            "acting",
            {
                "kind": "tool",
                "tool": "odd;tool#",
                "ok": False,
                "content": "boom;\nNote over O: injected",
                "metadata": {},
            },
        ),
        EventRecord(run_id, 5, "2026-11-07T18:00:05+00:00", "run_failed", "failed", {"reason": 'x;"y"\nz', "steps": 1}),
    ]

    lines = render_mermaid(events, include_content=True).splitlines()

    assert lines == [
        "sequenceDiagram",
        "    autonumber",
        "    participant O as Orchestrator",
        "    participant T1 as odd#59;tool#35;",
        "    Note over O: run weird #35;1#59; #34;q#34; #60;b#62;#38;amp#59; #37;#37;x end (provider fake)",
        "    O->>T1: call_tool (model.requested-tool): a#59;b --#62;#62; end",
        "    T1--xO: error (tool_error): boom#59; Note over O: injected",
        "    Note over O: failed (_OTHER): x#59;#34;y#34; z",
    ]
    for line in lines[2:]:
        text = line.split(" as ", 1)[1] if line.startswith("    participant") else line.split(": ", 1)[1]
        assert not re.search(r'[;#"<>%]', _strip_entities(text))


def test_handoffs_bots_and_human_approver_are_participants(tmp_path: Path) -> None:
    """Bots, the handoff between them, and a human approval are drawn as participants and arrows."""

    provider = _ScriptedProvider("TOOL:checklist:ship", "HANDOFF:writer:draft the note", "DONE: drafted")
    events = _run(tmp_path, provider, run_id="crew-run", bots=True)
    log = SQLiteEventLog(tmp_path / "runs.sqlite")
    gate = HitlApprovalGate(
        approval_dir=tmp_path / "approvals", tools_requiring_approval=frozenset({"deploy", "shutdown"})
    )
    try:
        request = gate.request(run_id="crew-run", tool_name="deploy", payload="prod")
        record_approval(log, request)
        record_approval(log, gate.resolve(request.request_id, ApprovalDecision.APPROVED))
        waiting = gate.request(run_id="crew-run", tool_name="shutdown", payload="prod")
        record_approval(log, waiting)
        events = log.list_events("crew-run")
    finally:
        log.close()

    lines = render_mermaid(events).splitlines()

    assert lines[2:8] == [
        "    participant O as Orchestrator",
        "    participant A1 as planner",
        "    participant A2 as writer",
        "    participant T1 as checklist",
        "    actor H as Human approver",
        "    Note over O: run crew-run (provider openai)",
    ]
    assert "    A1-->>O: HANDOFF writer" in lines
    assert "    A1->>A2: handoff (model.requested-handoff)" in lines
    assert "    O->>A2: call_llm (handoff.needs-continuation)" in lines
    # A pending request resolved later is one question and one answer; an open one gets a note.
    assert lines[-5:] == [
        "    O->>H: approve deploy?",
        "    H-->>O: approved",
        "    O->>H: approve shutdown?",
        "    Note over H: pending",
        "    Note over O: succeeded after 6 steps",
    ]


def test_mcp_servers_are_participants(tmp_path: Path) -> None:
    """MCP tools are grouped under one participant per server."""

    log = SQLiteEventLog(tmp_path / "runs.sqlite")
    decision = {
        "action": "call_tool",
        "target": "mcp__notes__search_notes",
        "payload": {"text": "release"},
        "rationale": {
            "rule_id": "model.requested-tool",
            "explanation": "",
            "observations_used": [],
            "rejected_actions": [],
        },
    }
    try:
        log.append("mcp-run", RunState.CREATED, EventType.RUN_CREATED, {"goal": "g", "provider": "fake"})
        log.append("mcp-run", RunState.DECIDING, EventType.DECISION, decision)
        log.append("mcp-run", RunState.ACTING, EventType.ACTION_REQUESTED, decision)
        log.append(
            "mcp-run",
            RunState.ACTING,
            EventType.ACTION_RESULT,
            {
                "kind": "tool",
                "tool": "mcp__notes__search_notes",
                "ok": True,
                "content": "release-checklist: freeze main",
                "metadata": {"mcp_server": "notes", "mcp_tool": "search_notes", "mcp_era": "modern"},
            },
        )
        events = log.list_events("mcp-run")
    finally:
        log.close()

    lines = render_mermaid(events).splitlines()

    assert "    participant T1 as MCP notes" in lines
    assert "    O->>T1: call_tool search_notes (model.requested-tool)" in lines
    assert "    T1-->>O: ok" in lines
    assert lines[-1] == "    Note over O: unfinished (no terminal event)"


def test_failures_interruptions_and_resumes_are_visible(tmp_path: Path) -> None:
    """Provider errors, an interrupted call, and a resume are drawn explicitly."""

    events = _run(tmp_path, _ScriptedProvider(RuntimeError("HTTP Error 503: Service Unavailable")), run_id="down")
    lines = render_mermaid(events).splitlines()
    assert "    A1--xO: error (503): HTTP Error 503: Service Unavailable" in lines
    assert lines[-1] == "    Note over O: failed (503): HTTP Error 503: Service Unavailable"

    class _CrashError(BaseException):
        """Stands in for the process dying mid-call."""

    log = SQLiteEventLog(tmp_path / "resume.sqlite")

    def runner(provider: _ScriptedProvider) -> AgentRunner:
        return AgentRunner(
            provider=provider,
            event_log=log,
            tools=build_default_tools(root=tmp_path),
            safety_policy=SafetyPolicy(max_steps=8, allowed_tools=frozenset({"checklist"})),
        )

    try:
        with pytest.raises(_CrashError):
            runner(_ScriptedProvider("TOOL:checklist:ship", _CrashError())).run(GOAL, run_id="crash")
        assert runner(_ScriptedProvider("DONE: back")).resume("crash").state == RunState.SUCCEEDED
        events = log.list_events("crash")
    finally:
        log.close()

    lines = render_mermaid(events).splitlines()
    interrupted = lines.index("    A1--xO: interrupted (no result recorded)")
    assert lines[interrupted + 1] == "    Note over O: resumed from checkpoint"
    assert lines[interrupted + 2] == "    O->>A1: call_llm (tool.result-needs-synthesis)"
    assert lines[-1] == "    Note over O: succeeded after 4 steps"


def test_unfinished_action_is_noted(tmp_path: Path) -> None:
    """A run cut off mid-call shows the open call and no terminal state."""

    events = _run(tmp_path, FakeLLMAdapter(), run_id="cut")
    first_request = next(event.seq for event in events if event.event_type == "action_requested")
    lines = render_mermaid([event for event in events if event.seq <= first_request]).splitlines()

    assert lines[-3:] == [
        "    O->>A1: call_llm (observe.no-model-output)",
        "    Note over A1: no result recorded",
        "    Note over O: unfinished (no terminal event)",
    ]
