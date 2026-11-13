"""Render a run as a Mermaid ``sequenceDiagram`` that GitHub renders inline.

Participants are the orchestrator, the model-backed agents (each registered bot, or the
provider when no bot is active), every built-in tool, every MCP server, and a human approver.
Messages are provider calls, tool calls and results, handoffs, and approvals, each labelled
with the decision's rule id. Content (model output, tool arguments and results, handoff
summaries) is shown only with ``include_content`` and is always redacted. Text is escaped
with Mermaid entity codes, so ``#``, ``;``, quotes, and line breaks cannot break the diagram.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

from multi_bot_agentic.event_log import EventRecord
from multi_bot_agentic.tracing.privacy import MAX_ERROR_CHARS, redact_text, redact_value
from multi_bot_agentic.tracing.spans import (
    classify_failure,
    mcp_identity,
    model_directive,
    run_error_type,
    tool_arguments,
    tool_error_type,
)
from multi_bot_agentic.tracing.timeline import (
    Approval,
    FinalDecision,
    Handoff,
    ModelCall,
    Resume,
    RunTimeline,
    ToolCall,
    parse_run,
)

# Longest content snippet (characters, before escaping) shown on one arrow.
SNIPPET_CHARS: Final[int] = 48
_INDENT: Final[str] = "    "
# Characters with a meaning in Mermaid syntax or HTML labels, replaced by entity codes.
_SPECIAL: Final[frozenset[str]] = frozenset('#;"%<>&`{}')


def mermaid_text(text: str, limit: int | None = None) -> str:
    """Escape ``text`` for a Mermaid message, note, or participant label.

    Whitespace runs (including line breaks) collapse to one space, the text is cut to
    ``limit`` characters, and syntax characters plus every non-ASCII character become
    numeric entity codes such as ``#35;``.

    Args:
        text: Raw text.
        limit: Optional maximum length before escaping.

    Returns:
        Escaped single-line ASCII text.
    """

    collapsed = " ".join(text.split())
    if limit is not None and len(collapsed) > limit:
        collapsed = collapsed[: max(0, limit - 3)].rstrip() + "..."
    return "".join(
        f"#{ord(character)};" if character in _SPECIAL or not " " <= character <= "~" else character
        for character in collapsed
    )


def render_mermaid(
    events: Sequence[EventRecord],
    *,
    include_content: bool = False,
    agent_name: str | None = None,
) -> str:
    """Render one run as a Mermaid sequence diagram.

    Args:
        events: Every event of exactly one run.
        include_content: Append short, redacted content snippets to messages.
        agent_name: Optional label for the orchestrator participant.

    Returns:
        Mermaid source starting with ``sequenceDiagram`` (no trailing newline).

    Raises:
        TraceInputError: If the events are empty, mix runs, or carry invalid timestamps.
    """

    return _MermaidRenderer(parse_run(events), include_content=include_content, agent_name=agent_name).render()


@dataclass(frozen=True)
class _Participant:
    """A declared participant."""

    alias: str
    label: str
    actor: bool = False


class _MermaidRenderer:
    """Turns a :class:`RunTimeline` into Mermaid lines."""

    def __init__(self, timeline: RunTimeline, *, include_content: bool, agent_name: str | None) -> None:
        self.timeline = timeline
        self.include_content = include_content
        label = agent_name.strip() if agent_name and agent_name.strip() else "Orchestrator"
        self.orchestrator = _Participant("O", label)
        self.agents: dict[str | None, _Participant] = {}
        self.tools: dict[str, _Participant] = {}
        self.human: _Participant | None = None
        self._asked: set[str] = set()
        self._resolved = {
            step.request_id
            for step in timeline.steps
            if isinstance(step, Approval) and step.request_id is not None and step.status in {"approved", "rejected"}
        }
        self._collect_participants()

    def render(self) -> str:
        """Return the diagram source."""

        timeline = self.timeline
        lines = ["sequenceDiagram", f"{_INDENT}autonumber"]
        participants = [self.orchestrator, *self.agents.values(), *self.tools.values()]
        if self.human is not None:
            participants.append(self.human)
        for participant in participants:
            keyword = "actor" if participant.actor else "participant"
            lines.append(f"{_INDENT}{keyword} {participant.alias} as {mermaid_text(participant.label)}")
        header = f"run {timeline.run_id}"
        if timeline.provider:
            header += f" (provider {timeline.provider})"
        lines.append(self._note(header))
        for step in timeline.steps:
            if isinstance(step, ModelCall):
                lines.extend(self._model_call(step))
            elif isinstance(step, ToolCall):
                lines.extend(self._tool_call(step))
            elif isinstance(step, Handoff):
                lines.append(self._handoff(step))
            elif isinstance(step, Approval):
                lines.extend(self._approval(step))
            elif isinstance(step, FinalDecision):
                decision = step.decision
                lines.append(self._note(f"{decision.action} ({decision.rule_id})"))
            elif isinstance(step, Resume):
                lines.append(self._note("resumed from checkpoint"))
        lines.append(self._outcome())
        return "\n".join(lines)

    def _collect_participants(self) -> None:
        """Declare agents, tools, MCP servers, and the human in order of first appearance."""

        if self.timeline.initial_bot is not None:
            self._agent(self.timeline.initial_bot)
        for step in self.timeline.steps:
            if isinstance(step, ModelCall):
                self._agent(step.agent)
            elif isinstance(step, ToolCall):
                self._tool(step)
            elif isinstance(step, Handoff):
                self._agent(step.from_bot)
                self._agent(step.to_bot)
            elif isinstance(step, Approval) and self.human is None:
                self.human = _Participant("H", "Human approver", actor=True)

    def _agent(self, bot: str | None) -> _Participant:
        """Return (declaring on first use) the participant of a bot, or of the provider."""

        participant = self.agents.get(bot)
        if participant is None:
            label = bot if bot is not None else f"LLM {self.timeline.provider or 'provider'}"
            participant = _Participant(f"A{len(self.agents) + 1}", label)
            self.agents[bot] = participant
        return participant

    def _tool(self, call: ToolCall) -> _Participant:
        """Return (declaring on first use) the participant of a tool or its MCP server."""

        mcp = mcp_identity(call)
        key = f"mcp:{mcp[0]}" if mcp is not None else f"tool:{call.tool}"
        participant = self.tools.get(key)
        if participant is None:
            label = f"MCP {mcp[0]}" if mcp is not None else call.tool
            participant = _Participant(f"T{len(self.tools) + 1}", label)
            self.tools[key] = participant
        return participant

    def _model_call(self, call: ModelCall) -> list[str]:
        """Return the request and reply arrows of a provider call."""

        agent = self._agent(call.agent).alias
        lines = [self._arrow("O", "->>", agent, f"call_llm ({call.decision.rule_id})")]
        if call.output is not None:
            kind, target = model_directive(call.output)
            reply = {"tool": "TOOL", "handoff": "HANDOFF", "done": "DONE", "text": "reply"}[kind]
            if target:
                reply += f" {target}"
            if self.include_content:
                reply += f": {self._snippet(_directive_payload(kind, call.output))}"
            lines.append(self._arrow(agent, "-->>", "O", reply))
        elif call.interrupted:
            lines.append(self._arrow(agent, "--x", "O", "interrupted (no result recorded)"))
        elif call.failure is not None:
            lines.append(
                self._arrow(agent, "--x", "O", self._error_label(classify_failure(call.failure), call.failure))
            )
        else:
            lines.append(self._note("no result recorded", over=agent))
        return lines

    def _tool_call(self, call: ToolCall) -> list[str]:
        """Return the request and result arrows of a tool call."""

        participant = self._tool(call).alias
        mcp = mcp_identity(call)
        request = "call_tool" + (f" {mcp[1]}" if mcp is not None else "")
        request += f" ({call.decision.rule_id})"
        if self.include_content:
            request += f": {self._snippet(_compact(tool_arguments(call)))}"
        lines = [self._arrow("O", "->>", participant, request)]
        error_type = tool_error_type(call)
        if call.ok:
            reply = "ok"
            if self.include_content and call.content is not None:
                reply += f": {self._snippet(call.content)}"
            lines.append(self._arrow(participant, "-->>", "O", reply))
        elif error_type is not None:
            lines.append(
                self._arrow(participant, "--x", "O", self._error_label(error_type, call.content or call.failure))
            )
        else:
            lines.append(self._note("no result recorded", over=participant))
        return lines

    def _handoff(self, handoff: Handoff) -> str:
        """Return the arrow of a handoff between bots."""

        source = self._agent(handoff.from_bot).alias
        target = self._agent(handoff.to_bot).alias
        label = f"handoff ({handoff.decision.rule_id})" if handoff.completed else "handoff rejected"
        if self.include_content and handoff.summary:
            label += f": {self._snippet(handoff.summary)}"
        return self._arrow(source, "->>" if handoff.completed else "-x", target, label)

    def _approval(self, approval: Approval) -> list[str]:
        """Return the request and answer arrows of a human approval.

        A request recorded as ``pending`` and resolved later is drawn as one question and
        one answer; a request that is still pending at the end of the log gets a note.
        """

        lines: list[str] = []
        key = approval.request_id
        if key is None or key not in self._asked:
            lines.append(self._arrow("O", "->>", "H", f"approve {approval.tool}?"))
            if key is not None:
                self._asked.add(key)
        if approval.status == "approved":
            lines.append(self._arrow("H", "-->>", "O", "approved"))
        elif approval.status == "rejected":
            lines.append(self._arrow("H", "--x", "O", "rejected"))
        elif key is None or key not in self._resolved:
            lines.append(self._note(approval.status, over="H"))
        return lines

    def _outcome(self) -> str:
        """Return the closing note with the run's terminal state."""

        outcome = self.timeline.outcome
        if outcome is None:
            return self._note("unfinished (no terminal event)")
        if outcome.state == "failed":
            error_type = run_error_type(self.timeline) or "_OTHER"
            return self._note(self._error_label(error_type, outcome.reason, prefix="failed"))
        text = outcome.state
        if outcome.steps is not None:
            text += f" after {outcome.steps} step{'' if outcome.steps == 1 else 's'}"
        if outcome.state == "cancelled" and outcome.reason:
            text += f": {redact_text(outcome.reason, SNIPPET_CHARS)}"
        return self._note(text)

    def _error_label(self, error_type: str, message: str | None, *, prefix: str = "error") -> str:
        """Return ``<prefix> (<type>)`` plus a short redacted message."""

        label = f"{prefix} ({error_type})"
        if message:
            label += f": {redact_text(message, MAX_ERROR_CHARS)}"
        return label

    def _snippet(self, text: str) -> str:
        """Return a short redacted content snippet."""

        return redact_text(text, SNIPPET_CHARS * 2)

    def _arrow(self, source: str, arrow: str, target: str, text: str) -> str:
        """Return one message line."""

        return f"{_INDENT}{source}{arrow}{target}: {mermaid_text(text, SNIPPET_CHARS * 2)}"

    def _note(self, text: str, *, over: str = "O") -> str:
        """Return one note line."""

        return f"{_INDENT}Note over {over}: {mermaid_text(text, SNIPPET_CHARS * 2)}"


def _compact(arguments: Mapping[str, Any]) -> str:
    """Return redacted tool arguments as short text: the bare payload for ``{"text": ...}``."""

    redacted = redact_value(arguments)
    if isinstance(redacted, dict) and set(redacted) == {"text"} and isinstance(redacted["text"], str):
        return str(redacted["text"])
    return json.dumps(redacted, sort_keys=True)


def _directive_payload(kind: str, output: str) -> str:
    """Return the part of a model output after its ``TOOL:``/``HANDOFF:``/``DONE:`` directive."""

    if kind in {"tool", "handoff"}:
        parts = output.split(":", 2)
        return parts[2] if len(parts) == 3 else ""
    if kind == "done":
        return output.removeprefix("DONE:").strip()
    return output
