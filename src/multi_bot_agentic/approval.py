"""Human-in-the-loop approval gate for sensitive tool calls.

Persists pending approval requests as JSON files under a configured directory.
Operators (or an external UI) resolve requests by rewriting the same files.

This is intentionally thinner than LangGraph interrupt/resume or CrewAI/AutoGen
human-input loops: no runner rewiring is required for v1. Callers check
``requires_approval``, create a request, poll until resolved, then continue.
Compatible with GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 tool flows.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from uuid import uuid4


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
