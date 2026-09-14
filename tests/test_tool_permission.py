"""Tests for ToolPermissionAllowlist."""

from __future__ import annotations

import pytest

from multi_bot_agentic.tool_permission import (
    ToolPermissionAllowlist,
    ToolPermissionDecision,
)


def test_grant_then_check_allows() -> None:
    """Granted tools are allowed for that bot."""

    acl = ToolPermissionAllowlist()
    acl.grant("researcher", "search")
    result = acl.check("researcher", "search")
    assert result.decision is ToolPermissionDecision.ALLOWED
    assert result.bot_id == "researcher"
    assert result.tool_name == "search"
    assert "grant" in result.reason


def test_default_deny_without_grant() -> None:
    """Unknown bots are denied when default_deny is True."""

    acl = ToolPermissionAllowlist(default_deny=True)
    result = acl.check("researcher", "shell")
    assert result.decision is ToolPermissionDecision.DENIED
    assert "default deny" in result.reason


def test_grant_does_not_leak_across_bots() -> None:
    """A grant for one bot does not authorize another bot."""

    acl = ToolPermissionAllowlist()
    acl.grant("researcher", "search")
    other = acl.check("writer", "search")
    assert other.decision is ToolPermissionDecision.DENIED


def test_revoke_removes_grant() -> None:
    """revoke drops a grant and subsequent checks deny."""

    acl = ToolPermissionAllowlist()
    acl.grant("bot-a", "checklist")
    assert acl.revoke("bot-a", "checklist") is True
    assert acl.check("bot-a", "checklist").decision is ToolPermissionDecision.DENIED
    assert acl.revoke("bot-a", "checklist") is False


def test_grants_for_returns_frozen_set() -> None:
    """grants_for lists only the tools granted to that bot."""

    acl = ToolPermissionAllowlist()
    acl.grant("bot-a", "search")
    acl.grant("bot-a", "summarize")
    acl.grant("bot-b", "shell")
    assert acl.grants_for("bot-a") == frozenset({"search", "summarize"})
    assert acl.grants_for("bot-b") == frozenset({"shell"})
    assert acl.grants_for("missing") == frozenset()


def test_default_allow_when_no_grants() -> None:
    """With default_deny=False, bots without grants are allowed."""

    acl = ToolPermissionAllowlist(default_deny=False)
    result = acl.check("any-bot", "any-tool")
    assert result.decision is ToolPermissionDecision.ALLOWED
    assert "default allow" in result.reason


def test_explicit_empty_grants_still_deny_under_default_allow() -> None:
    """Once a bot has a grant set, non-granted tools are denied even if default_allow."""

    acl = ToolPermissionAllowlist(default_deny=False)
    acl.grant("bot-a", "search")
    acl.revoke("bot-a", "search")
    # After revoke emptied the set, bot has no grants recorded again.
    assert acl.check("bot-a", "shell").decision is ToolPermissionDecision.ALLOWED
    acl.grant("bot-a", "search")
    denied = acl.check("bot-a", "shell")
    assert denied.decision is ToolPermissionDecision.DENIED
    assert "not in bot allowlist" in denied.reason


def test_rejects_empty_ids() -> None:
    """Empty bot_id or tool_name raises ValueError."""

    acl = ToolPermissionAllowlist()
    with pytest.raises(ValueError, match="bot_id"):
        acl.grant("  ", "search")
    with pytest.raises(ValueError, match="tool_name"):
        acl.grant("bot", "")
    with pytest.raises(ValueError, match="bot_id"):
        acl.check("", "search")
    with pytest.raises(ValueError, match="tool_name"):
        acl.revoke("bot", " ")
    with pytest.raises(ValueError, match="bot_id"):
        acl.grants_for("  ")
