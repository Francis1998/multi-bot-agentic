"""Tests for HitlApprovalGate."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from multi_bot_agentic.approval import ApprovalDecision, ApprovalRequest, HitlApprovalGate


def test_requires_approval_and_request_persists_pending_json(tmp_path: Path) -> None:
    """Gated tools create pending JSON files under approval_dir."""

    gate = HitlApprovalGate(
        approval_dir=tmp_path / "approvals",
        tools_requiring_approval=frozenset({"shell", "deploy"}),
    )
    assert gate.requires_approval("shell") is True
    assert gate.requires_approval("echo") is False

    request = gate.request(run_id="run-1", tool_name="shell", payload="rm -rf /tmp/demo")
    assert isinstance(request, ApprovalRequest)
    assert request.status is ApprovalDecision.PENDING
    path = tmp_path / "approvals" / f"{request.request_id}.json"
    assert path.is_file()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["status"] == "pending"
    assert payload["tool_name"] == "shell"
    assert gate.poll(request.request_id) is ApprovalDecision.PENDING


def test_resolve_approve_and_reject(tmp_path: Path) -> None:
    """resolve updates status; poll reflects the final decision."""

    gate = HitlApprovalGate(
        approval_dir=tmp_path / "approvals",
        tools_requiring_approval=frozenset({"deploy"}),
    )
    approved = gate.request(run_id="run-a", tool_name="deploy", payload="prod")
    rejected = gate.request(run_id="run-b", tool_name="deploy", payload="staging")

    done = gate.resolve(approved.request_id, ApprovalDecision.APPROVED)
    assert done.status is ApprovalDecision.APPROVED
    assert gate.poll(approved.request_id) is ApprovalDecision.APPROVED

    denied = gate.resolve(rejected.request_id, ApprovalDecision.REJECTED)
    assert denied.status is ApprovalDecision.REJECTED
    assert gate.poll(rejected.request_id) is ApprovalDecision.REJECTED


def test_resolve_rejects_pending_and_double_resolve(tmp_path: Path) -> None:
    """PENDING decisions and double-resolve attempts raise ValueError."""

    gate = HitlApprovalGate(
        approval_dir=tmp_path,
        tools_requiring_approval=frozenset({"shell"}),
    )
    request = gate.request(run_id="run-1", tool_name="shell", payload="ls")
    with pytest.raises(ValueError, match="approved or rejected"):
        gate.resolve(request.request_id, ApprovalDecision.PENDING)
    gate.resolve(request.request_id, ApprovalDecision.APPROVED)
    with pytest.raises(ValueError, match="already resolved"):
        gate.resolve(request.request_id, ApprovalDecision.REJECTED)


def test_request_rejects_ungated_tool_and_empty_ids(tmp_path: Path) -> None:
    """Ungated tools and empty identifiers raise ValueError."""

    gate = HitlApprovalGate(
        approval_dir=tmp_path,
        tools_requiring_approval=frozenset({"shell"}),
    )
    with pytest.raises(ValueError, match="does not require approval"):
        gate.request(run_id="run-1", tool_name="echo", payload="hi")
    with pytest.raises(ValueError, match="run_id"):
        gate.request(run_id="  ", tool_name="shell", payload="x")
    with pytest.raises(ValueError, match="tool_name"):
        gate.request(run_id="run-1", tool_name="", payload="x")


def test_constructor_rejects_empty_tool_set(tmp_path: Path) -> None:
    """An empty tools_requiring_approval set raises ValueError."""

    with pytest.raises(ValueError, match="tools_requiring_approval"):
        HitlApprovalGate(approval_dir=tmp_path, tools_requiring_approval=frozenset())
