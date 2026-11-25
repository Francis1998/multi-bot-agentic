"""Human-in-the-loop approvals: durable run interrupts and a file-backed approval gate.

Two layers share :class:`ApprovalDecision`:

* **Run interrupts, wired into the runner.** With ``SafetyPolicy.require_approval`` (CLI
  ``--require-approval``), a ``call_tool`` decision for a matching tool pauses the run before the
  tool executes: the runner appends an ``interrupt`` event, writes a checkpoint, moves the run to
  ``awaiting_approval``, and returns. :func:`decide_interrupt` (CLI ``approve`` / ``reject``)
  appends an ``approval_decision`` event saying who decided, when, why, and whether the arguments
  were edited. ``resume`` then executes the approved (possibly edited) call exactly once, or feeds
  the rejection back to the model as an observation so it re-plans. The design follows LangGraph
  ``interrupt()`` / ``Command(resume=...)``, the OpenAI Agents SDK ``needs_approval`` /
  ``RunState.approve()``, and Pydantic AI deferred tools (``requires_approval``), on top of the
  existing event log and checkpoints instead of a separate store.
* **File-backed gate, caller-driven.** :class:`HitlApprovalGate` persists approval requests as JSON
  files for callers that run their own polling loop, and :func:`record_approval` mirrors a request
  or decision into a run's event log. This API is unchanged.

Compatible with GPT-6.2 Sol / Claude Opus 5.5 / Gemini 4 Neon / Kimi K3.1 Pro tool flows.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Final
from uuid import uuid4

from multi_bot_agentic.event_log import EventRecord, SQLiteEventLog
from multi_bot_agentic.models import Decision, EventType, Observation, RunState

# ``kind`` of an ``interrupt`` event that asks a human to approve one tool call.
INTERRUPT_KIND: Final[str] = "tool_approval"
# Longest argument preview (characters) an interrupt records for listings.
PREVIEW_CHARS: Final[int] = 240
# Longest replacement arguments (characters of JSON) ``approve --args`` accepts.
MAX_EDITED_ARGUMENTS_CHARS: Final[int] = 65_536
# Longest reason (characters) a decision records; a rejection reason is shown to the model.
MAX_REASON_CHARS: Final[int] = 1_000
# Observation source prefix of a rejection fed back to the model (``approval:<tool>``).
REJECTION_SOURCE_PREFIX: Final[str] = "approval:"
_TERMINAL_EVENTS: Final[frozenset[str]] = frozenset(
    {EventType.RUN_COMPLETED.value, EventType.RUN_FAILED.value, EventType.RUN_CANCELLED.value}
)


class ApprovalError(ValueError):
    """An interrupt cannot be decided or resumed as requested. Nothing was written."""


class AwaitingApprovalError(ApprovalError):
    """A paused run was resumed before a human approved or rejected its interrupt.

    Attributes:
        interrupt: The interrupt the run is paused at.
    """

    def __init__(self, interrupt: InterruptRecord) -> None:
        self.interrupt = interrupt
        super().__init__(
            f"run {interrupt.run_id} is awaiting approval of interrupt {interrupt.interrupt_id} "
            f"({interrupt.tool} in step {interrupt.step}); approve or reject it before resuming"
        )


class ApprovalDecision(str, Enum):
    """Lifecycle status for one approval request.

    Note:
        Exposed as ``(str, Enum)`` so Python 3.10 CI stays green (``StrEnum`` is 3.11+).
    """

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass(frozen=True)
class ApprovalRequest:
    """Persisted approval request for a sensitive tool invocation.

    Attributes:
        request_id: Stable request identifier (also the JSON filename stem).
        run_id: Agent run that triggered the request.
        tool_name: Tool that requires human approval.
        payload: Opaque tool payload text.
        status: Current approval decision.
    """

    request_id: str
    run_id: str
    tool_name: str
    payload: str
    status: ApprovalDecision


class HitlApprovalGate:
    """File-backed approval gate for allowlisted sensitive tools.

    Args:
        approval_dir: Directory where request JSON files are stored.
        tools_requiring_approval: Tool names that must pause for human review.
    """

    def __init__(self, *, approval_dir: Path, tools_requiring_approval: frozenset[str]) -> None:
        if not tools_requiring_approval:
            raise ValueError("tools_requiring_approval must be non-empty")
        self._approval_dir = Path(approval_dir)
        self._approval_dir.mkdir(parents=True, exist_ok=True)
        self._tools_requiring_approval = frozenset(tools_requiring_approval)

    def requires_approval(self, tool_name: str) -> bool:
        """Return whether ``tool_name`` is gated.

        Args:
            tool_name: Candidate tool identifier.

        Returns:
            ``True`` when the tool is in the approval set.
        """

        return tool_name in self._tools_requiring_approval

    def request(self, *, run_id: str, tool_name: str, payload: str) -> ApprovalRequest:
        """Create a pending approval request and persist it as JSON.

        Args:
            run_id: Owning run identifier.
            tool_name: Tool that needs approval (must be gated).
            payload: Tool payload text.

        Returns:
            Newly created pending request.

        Raises:
            ValueError: When identifiers are empty or the tool is not gated.
        """

        if not run_id.strip():
            raise ValueError("run_id must be non-empty")
        if not tool_name.strip():
            raise ValueError("tool_name must be non-empty")
        if not self.requires_approval(tool_name):
            raise ValueError(f"tool does not require approval: {tool_name}")
        request = ApprovalRequest(
            request_id=str(uuid4()),
            run_id=run_id.strip(),
            tool_name=tool_name.strip(),
            payload=payload,
            status=ApprovalDecision.PENDING,
        )
        self._write(request)
        return request

    def resolve(self, request_id: str, decision: ApprovalDecision) -> ApprovalRequest:
        """Resolve a pending request to approved or rejected.

        Args:
            request_id: Existing request identifier.
            decision: Final decision (must not be ``PENDING``).

        Returns:
            Updated request.

        Raises:
            ValueError: Invalid decision or unknown/already-resolved request.
            FileNotFoundError: When the request file is missing.
        """

        if decision is ApprovalDecision.PENDING:
            raise ValueError("decision must be approved or rejected")
        current = self._read(request_id)
        if current.status is not ApprovalDecision.PENDING:
            raise ValueError(f"request already resolved: {current.status.value}")
        updated = ApprovalRequest(
            request_id=current.request_id,
            run_id=current.run_id,
            tool_name=current.tool_name,
            payload=current.payload,
            status=decision,
        )
        self._write(updated)
        return updated

    def poll(self, request_id: str) -> ApprovalDecision:
        """Return the current decision for ``request_id``.

        Args:
            request_id: Existing request identifier.

        Returns:
            Current ``ApprovalDecision``.
        """

        return self._read(request_id).status

    def _path_for(self, request_id: str) -> Path:
        safe_id = request_id.strip()
        if not safe_id or "/" in safe_id or "\\" in safe_id or ".." in safe_id:
            raise ValueError("request_id must be a plain identifier")
        return self._approval_dir / f"{safe_id}.json"

    def _write(self, request: ApprovalRequest) -> None:
        payload = asdict(request)
        payload["status"] = request.status.value
        path = self._path_for(request.request_id)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _read(self, request_id: str) -> ApprovalRequest:
        path = self._path_for(request_id)
        raw = json.loads(path.read_text(encoding="utf-8"))
        return ApprovalRequest(
            request_id=str(raw["request_id"]),
            run_id=str(raw["run_id"]),
            tool_name=str(raw["tool_name"]),
            payload=str(raw["payload"]),
            status=ApprovalDecision(str(raw["status"])),
        )


def record_approval(
    event_log: SQLiteEventLog,
    request: ApprovalRequest,
    *,
    state: RunState = RunState.ACTING,
) -> EventRecord:
    """Append an approval request or decision to the run's durable event log.

    The event is an ``action_result`` with ``kind: "approval"``, so ``replay`` lists it and
    ``trace`` exports it as a span event and a human-approver message. Only identifiers and
    the decision are recorded, never the tool payload text.

    Args:
        event_log: Event log of the run that requested the approval.
        request: Approval request in its current status.
        state: Run state to record with the event.

    Returns:
        The persisted event.
    """

    return event_log.append(
        request.run_id,
        state,
        EventType.ACTION_RESULT,
        {
            "kind": "approval",
            "request_id": request.request_id,
            "tool": request.tool_name,
            "status": request.status.value,
        },
    )


@dataclass(frozen=True)
class InterruptDecision:
    """A human's answer to one interrupt: the first ``approval_decision`` event recorded for it.

    Attributes:
        decision: ``approved`` or ``rejected``.
        decided_by: Who decided (``--by``, default the OS user).
        decided_at: When, as an ISO 8601 UTC timestamp.
        reason: Why, if given (required for rejections; shown to the model).
        arguments: Replacement arguments when the approver edited the call, else ``None``.
        arguments_preview: Redacted, truncated preview of the replacement arguments.
        seq: Sequence number of the ``approval_decision`` event.
    """

    decision: ApprovalDecision
    decided_by: str
    decided_at: str
    reason: str | None
    arguments: Mapping[str, Any] | None
    arguments_preview: str | None
    seq: int

    @property
    def args_edited(self) -> bool:
        """Return whether the approver replaced the call's arguments."""

        return self.arguments is not None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dictionary (replacement arguments only as a preview)."""

        return {
            "decision": self.decision.value,
            "decided_by": self.decided_by,
            "decided_at": self.decided_at,
            "reason": self.reason,
            "args_edited": self.args_edited,
            "arguments_preview": self.arguments_preview,
        }


@dataclass(frozen=True)
class InterruptRecord:
    """One human-approval interrupt of a run, rebuilt from the event log.

    Attributes:
        interrupt_id: Stable identifier (``int-`` + 12 hex digits).
        run_id: Run that paused.
        seq: Sequence number of the ``interrupt`` event.
        requested_at: Timestamp of the ``interrupt`` event.
        step: The paused step, numbered like ``history`` (the first loop step is 1).
        tool: Tool the model asked to call.
        bot: Bot that was active, if any.
        arguments: Arguments of the requested call.
        arguments_preview: Redacted, truncated preview of ``arguments``.
        rule_id: Decision rule that selected the call.
        explanation: Rationale of that rule.
        policy: ``require_approval`` entries that matched the tool.
        decision: The human decision, or ``None`` while undecided.
        paused: True while the run's latest checkpoint is this interrupt and nothing happened since
            (other than the decision): ``resume`` acts on it.
        executed: True once an approved call recorded its tool result.
    """

    interrupt_id: str
    run_id: str
    seq: int
    requested_at: str
    step: int
    tool: str
    bot: str | None
    arguments: Mapping[str, Any]
    arguments_preview: str
    rule_id: str | None
    explanation: str | None
    policy: tuple[str, ...]
    decision: InterruptDecision | None
    paused: bool
    executed: bool

    @property
    def status(self) -> str:
        """Return ``pending``, ``approved``, ``rejected``, or ``expired`` (the run moved on undecided)."""

        if self.decision is not None:
            return self.decision.decision.value
        return "pending" if self.paused else "expired"

    @property
    def effective_arguments(self) -> Mapping[str, Any]:
        """Return the arguments an approved call runs with: the edited ones, if any."""

        if self.decision is not None and self.decision.arguments is not None:
            return self.decision.arguments
        return self.arguments

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable summary (arguments only as a redacted preview)."""

        return {
            "interrupt_id": self.interrupt_id,
            "run_id": self.run_id,
            "step": self.step,
            "tool": self.tool,
            "bot": self.bot,
            "status": self.status,
            "requested_at": self.requested_at,
            "arguments_preview": self.arguments_preview,
            "rule_id": self.rule_id,
            "policy": list(self.policy),
            "decision": self.decision.to_dict() if self.decision is not None else None,
            "resumed": not self.paused and self.status != "expired",
            "executed": self.executed,
        }


def new_interrupt_id() -> str:
    """Return a fresh interrupt identifier such as ``int-3f9c2a7b1d4e``."""

    return f"int-{uuid4().hex[:12]}"


def argument_preview(arguments: Mapping[str, Any], limit: int = PREVIEW_CHARS) -> str:
    """Return a redacted, truncated JSON preview of tool arguments for humans.

    Secrets under sensitive keys (``api_key``, ``password``, ...) and emails, phone numbers, and
    tokens in text are replaced with the same scrubbers ``trace`` uses.

    Args:
        arguments: Tool arguments.
        limit: Maximum preview length before the truncation marker.

    Returns:
        Compact JSON text.
    """

    from multi_bot_agentic.tracing.privacy import redact_value

    text = json.dumps(redact_value(dict(arguments), limit), sort_keys=True, ensure_ascii=False)
    return text if len(text) <= limit else text[:limit] + "...[truncated]"


def interrupt_payload(
    decision: Decision,
    *,
    interrupt_id: str,
    step: int,
    bot: str | None,
    policy: Iterable[str],
) -> dict[str, Any]:
    """Build the payload of the ``interrupt`` event a gated ``call_tool`` decision records.

    Args:
        decision: The ``call_tool`` decision that needs approval.
        interrupt_id: Identifier from :func:`new_interrupt_id`.
        step: The paused step (``history`` numbering).
        bot: Active bot, if any.
        policy: ``require_approval`` entries that matched the tool.

    Returns:
        JSON-serializable payload.
    """

    return {
        "interrupt_id": interrupt_id,
        "kind": INTERRUPT_KIND,
        "tool": decision.target,
        "bot": bot,
        "step": step,
        "arguments": dict(decision.payload),
        "arguments_preview": argument_preview(decision.payload),
        "rationale": decision.rationale.to_dict(),
        "policy": sorted(set(policy)),
    }


def collect_interrupts(events: Iterable[EventRecord]) -> list[InterruptRecord]:
    """Rebuild every interrupt of the given events, run by run, oldest first.

    Args:
        events: Events of one or more runs, in any order.

    Returns:
        Interrupt records ordered by run (first appearance) and sequence number.
    """

    by_run: dict[str, list[EventRecord]] = {}
    for event in events:
        by_run.setdefault(event.run_id, []).append(event)
    records: list[InterruptRecord] = []
    for run_events in by_run.values():
        records.extend(_run_interrupts(sorted(run_events, key=lambda event: event.seq)))
    return records


def paused_interrupt(events: Iterable[EventRecord]) -> InterruptRecord | None:
    """Return the interrupt a run is paused at (decided or not), if any.

    Args:
        events: Every event of one run.

    Returns:
        The paused interrupt, or ``None`` when the run is not paused.
    """

    return next((record for record in reversed(collect_interrupts(events)) if record.paused), None)


def find_interrupt(event_log: SQLiteEventLog, interrupt_id: str, *, run_id: str | None = None) -> InterruptRecord:
    """Look up one interrupt by id (forks copy decided interrupts, so ids can repeat across runs).

    Args:
        event_log: Event log to search.
        interrupt_id: Interrupt identifier.
        run_id: Optional run to search in.

    Returns:
        The matching interrupt, preferring the one a run is paused at.

    Raises:
        ApprovalError: If no interrupt matches, or several runs are paused at it.
    """

    wanted = interrupt_id.strip()
    events = event_log.list_events(run_id) if run_id is not None else event_log.list_events()
    matches = [record for record in collect_interrupts(events) if record.interrupt_id == wanted]
    if not matches:
        scope = f" for run {run_id}" if run_id is not None else ""
        raise ApprovalError(
            f"interrupt {wanted} not found in event log {event_log.path}{scope}; list them with `approvals list --all`"
        )
    paused = [record for record in matches if record.paused]
    if len(paused) > 1:
        runs = ", ".join(record.run_id for record in paused)
        raise ApprovalError(f"interrupt {wanted} is paused in several runs ({runs}); pass --run-id")
    return paused[0] if paused else matches[0]


def find_paused_interrupt(event_log: SQLiteEventLog, run_id: str) -> InterruptRecord:
    """Return the interrupt ``run_id`` is paused at.

    Args:
        event_log: Event log holding the run.
        run_id: Run identifier.

    Returns:
        The paused interrupt.

    Raises:
        ApprovalError: If the run does not exist or is not paused at an interrupt.
    """

    events = event_log.list_events(run_id)
    if not events:
        raise ApprovalError(f"run {run_id} not found in event log {event_log.path}")
    record = paused_interrupt(events)
    if record is None:
        raise ApprovalError(f"run {run_id} is not paused at an interrupt (state {events[-1].state})")
    return record


def validate_edited_arguments(original: Mapping[str, Any], edited: Any) -> dict[str, Any]:
    """Check replacement arguments for an approved call.

    An edit changes values, not the call's shape: it must be a JSON object with exactly the keys of
    the requested call, each holding the same JSON type (``TOOL:`` directives always produce
    ``{"text": "..."}``), and at most :data:`MAX_EDITED_ARGUMENTS_CHARS` characters of JSON.

    Args:
        original: Arguments the model requested.
        edited: Parsed ``--args`` JSON.

    Returns:
        The replacement arguments.

    Raises:
        ApprovalError: If the edit is not acceptable.
    """

    if not isinstance(edited, dict):
        raise ApprovalError(f"--args must be a JSON object, got {_json_type(edited)}")
    expected = sorted(str(key) for key in original)
    if sorted(str(key) for key in edited) != expected:
        raise ApprovalError(
            f"--args must have exactly the keys of the requested call ({', '.join(expected) or 'none'}), "
            f"got {', '.join(sorted(str(key) for key in edited)) or 'none'}"
        )
    for key, value in original.items():
        if _json_type(edited[key]) != _json_type(value):
            raise ApprovalError(f"--args key {key!r} must be a {_json_type(value)}, got {_json_type(edited[key])}")
    try:
        size = len(json.dumps(edited, allow_nan=False))
    except ValueError as error:
        raise ApprovalError(f"--args is not plain JSON: {error}") from error
    if size > MAX_EDITED_ARGUMENTS_CHARS:
        raise ApprovalError(f"--args is {size} characters of JSON; the limit is {MAX_EDITED_ARGUMENTS_CHARS}")
    return dict(edited)


def decide_interrupt(
    event_log: SQLiteEventLog,
    interrupt_id: str | None,
    decision: ApprovalDecision,
    *,
    decided_by: str,
    reason: str | None = None,
    arguments: Any = None,
    run_id: str | None = None,
) -> InterruptRecord:
    """Record a human decision on the interrupt a run is paused at.

    The check and the ``approval_decision`` append are one atomic transaction, so the first
    decision wins even when two approvers race. Nothing is executed here: ``resume`` acts on it.

    Args:
        event_log: Event log holding the run.
        interrupt_id: Interrupt to decide, or ``None`` for the one ``run_id`` is paused at.
        decision: ``APPROVED`` or ``REJECTED``.
        decided_by: Who decides (recorded verbatim).
        reason: Why; required for a rejection, whose reason is shown to the model.
        arguments: Replacement arguments for an approval (parsed JSON), or ``None`` to keep them.
        run_id: Run to look in; required when ``interrupt_id`` is ``None``.

    Returns:
        The interrupt with its decision.

    Raises:
        ApprovalError: Invalid decision or arguments, unknown interrupt, already decided, or the run
            is no longer paused at it.
    """

    if decision is ApprovalDecision.PENDING:
        raise ApprovalError("decision must be approved or rejected")
    who = decided_by.strip()
    if not who:
        raise ApprovalError("--by must be non-empty")
    why = reason.strip() if reason is not None else ""
    if decision is ApprovalDecision.REJECTED and not why:
        raise ApprovalError("a rejection needs --reason; the model is told why its call was rejected")
    if len(why) > MAX_REASON_CHARS:
        raise ApprovalError(f"--reason is {len(why)} characters; the limit is {MAX_REASON_CHARS}")
    if decision is ApprovalDecision.REJECTED and arguments is not None:
        raise ApprovalError("--args edits an approved call; a rejected call never runs")
    if interrupt_id is None:
        if run_id is None:
            raise ApprovalError("give an interrupt id, or --run-id to decide the interrupt that run is paused at")
        record = find_paused_interrupt(event_log, run_id)
    else:
        record = find_interrupt(event_log, interrupt_id, run_id=run_id)
    _ensure_decidable(record)
    edited = validate_edited_arguments(record.arguments, arguments) if arguments is not None else None
    if edited is not None and edited == dict(record.arguments):
        edited = None
    payload: dict[str, Any] = {
        "interrupt_id": record.interrupt_id,
        "decision": decision.value,
        "tool": record.tool,
        "step": record.step,
        "decided_by": who,
        "decided_at": _utc_now(),
        "reason": why or None,
        "args_edited": edited is not None,
    }
    if edited is not None:
        payload["arguments"] = edited
        payload["arguments_preview"] = argument_preview(edited)

    def guard(events: list[EventRecord]) -> None:
        current = next((item for item in collect_interrupts(events) if item.interrupt_id == record.interrupt_id), None)
        if current is None:
            raise ApprovalError(f"interrupt {record.interrupt_id} disappeared from run {record.run_id}")
        _ensure_decidable(current)

    event_log.append_guarded(record.run_id, [(RunState.AWAITING_APPROVAL, EventType.APPROVAL_DECISION, payload)], guard)
    return find_interrupt(event_log, record.interrupt_id, run_id=record.run_id)


def rejection_observation(record: InterruptRecord) -> Observation:
    """Return the observation that tells the model a human rejected its tool call.

    Args:
        record: A rejected interrupt.

    Returns:
        Observation with source ``approval:<tool>``; the decision engine re-plans on it.
    """

    reason = (record.decision.reason if record.decision is not None else None) or "no reason given"
    return Observation(
        source=f"{REJECTION_SOURCE_PREFIX}{record.tool}",
        content=f"REJECTED:{record.tool}: a human reviewer rejected this tool call, so it did not run. "
        f"Reason: {reason}",
        metadata={"interrupt_id": record.interrupt_id, "decision": "rejected", "tool": record.tool, "reason": reason},
    )


def _ensure_decidable(record: InterruptRecord) -> None:
    """Raise unless ``record`` is still waiting for its first decision."""

    if record.decision is not None:
        done = record.decision
        raise ApprovalError(
            f"interrupt {record.interrupt_id} was already {done.decision.value} by {done.decided_by} "
            f"at {done.decided_at}; a decision cannot be changed"
        )
    if not record.paused:
        raise ApprovalError(f"interrupt {record.interrupt_id} expired: run {record.run_id} is no longer paused at it")


def _run_interrupts(events: Sequence[EventRecord]) -> list[InterruptRecord]:
    """Rebuild the interrupts of one run from its events (ordered by sequence number)."""

    found: dict[str, EventRecord] = {}
    decisions: dict[str, InterruptDecision] = {}
    checkpoints: dict[str, int] = {}
    executed: set[str] = set()
    latest_checkpoint: int | None = None
    for index, event in enumerate(events):
        payload = event.payload
        identifier = _optional_str(payload.get("interrupt_id"))
        if event.event_type == EventType.CHECKPOINT.value:
            latest_checkpoint = index
        if identifier is None:
            continue
        if event.event_type == EventType.INTERRUPT.value and identifier not in found:
            found[identifier] = event
        elif event.event_type == EventType.APPROVAL_DECISION.value and identifier in found:
            parsed = _parse_decision(event)
            if parsed is not None and identifier not in decisions:
                decisions[identifier] = parsed
        elif event.event_type == EventType.CHECKPOINT.value and identifier in found:
            checkpoints[identifier] = index
        elif event.event_type == EventType.ACTION_RESULT.value and identifier in found:
            executed.add(identifier)
    finished = any(event.event_type in _TERMINAL_EVENTS for event in events)
    records: list[InterruptRecord] = []
    for identifier, event in found.items():
        payload = event.payload
        anchor = checkpoints.get(identifier)
        moved_on = anchor is None or any(
            later.event_type != EventType.APPROVAL_DECISION.value for later in events[anchor + 1 :]
        )
        rationale = payload.get("rationale")
        rationale = rationale if isinstance(rationale, dict) else {}
        arguments = payload.get("arguments")
        policy = payload.get("policy")
        step = payload.get("step")
        records.append(
            InterruptRecord(
                interrupt_id=identifier,
                run_id=event.run_id,
                seq=event.seq,
                requested_at=event.timestamp,
                step=step if isinstance(step, int) and not isinstance(step, bool) else 0,
                tool=str(payload.get("tool") or "unknown"),
                bot=_optional_str(payload.get("bot")),
                arguments=dict(arguments) if isinstance(arguments, dict) else {},
                arguments_preview=str(payload.get("arguments_preview", "")),
                rule_id=_optional_str(rationale.get("rule_id")),
                explanation=_optional_str(rationale.get("explanation")),
                policy=tuple(str(item) for item in policy) if isinstance(policy, list) else (),
                decision=decisions.get(identifier),
                paused=not moved_on and not finished and anchor == latest_checkpoint,
                executed=identifier in executed,
            )
        )
    return records


def _parse_decision(event: EventRecord) -> InterruptDecision | None:
    """Parse an ``approval_decision`` event, ignoring malformed ones."""

    payload = event.payload
    try:
        decision = ApprovalDecision(str(payload.get("decision")))
    except ValueError:
        return None
    if decision is ApprovalDecision.PENDING:
        return None
    arguments = payload.get("arguments")
    edited = dict(arguments) if payload.get("args_edited") is True and isinstance(arguments, dict) else None
    return InterruptDecision(
        decision=decision,
        decided_by=str(payload.get("decided_by") or "unknown"),
        decided_at=str(payload.get("decided_at") or event.timestamp),
        reason=_optional_str(payload.get("reason")),
        arguments=edited,
        arguments_preview=_optional_str(payload.get("arguments_preview")) if edited is not None else None,
        seq=event.seq,
    )


def _json_type(value: Any) -> str:
    """Name the JSON type of a parsed value."""

    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, (list, tuple)):
        return "array"
    return "object" if isinstance(value, dict) else type(value).__name__


def _optional_str(value: Any) -> str | None:
    """Return a non-empty string or ``None``."""

    return value if isinstance(value, str) and value else None


def _utc_now() -> str:
    """Return the current UTC time as ISO 8601."""

    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
